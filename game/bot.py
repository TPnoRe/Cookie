"""game/bot.py -- Bot worker thread."""
import time
import logging
import traceback
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from game.state import BotState
from vision.engine import VisionEngine

log = logging.getLogger(__name__)


# A missing template for one frame is normal. Recovery has been removed
# to prevent prolonged crashes. Unknown states now just reset to IDLE.
_STATE_RECOVERY_TIMEOUT = 8.0


class BotThread(QThread):
    """Main bot loop running in a background thread."""

    stage_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    bot_finished = pyqtSignal()
    run_completed = pyqtSignal()

    def __init__(self, app, farm_mode='farm_gold'):
        super().__init__()
        self.app = app
        self.farm_mode = farm_mode
        self.state = BotState.IDLE
        self._stop_flag = False
        self._loop_interval = 0.3
        self._handlers = {}
        self._runs = 0
        self._engine = VisionEngine()
        self._state_unseen_since = None

    def run(self):
        #self.log_message.emit('ok', 'Bot started (%s)' % self.farm_mode)
        self._init_handlers()

        if self.farm_mode == 'open_gitbox':
            self._run_gitbox_mode()
            return

        while not self._stop_flag:
            if not self.app.emulator.connected:
                self.log_message.emit('warn', 'Emulator disconnected, waiting...')
                time.sleep(2)
                continue

            try:
                screenshot = self.app.emulator.screenshot()
                if screenshot is None:
                    time.sleep(1)
                    continue

                size = self.app.emulator.get_size()
                if not size:
                    time.sleep(1)
                    continue

                view_w, view_h = size
                stage = self._detect_stage(screenshot, view_w, view_h)

                if stage != self.state.value:
                    old = self.state.value
                    if old == 'results' and stage != 'results':
                        self._runs += 1
                        self.run_completed.emit()
                        #self.log_message.emit('ok', 'Results: run #%d completed!' % self._runs)
                        prep_h = self._handlers.get('prep')
                        if prep_h:
                            prep_h._fast_step = 0
                            prep_h._relay_step = 0
                            prep_h._boost_step = 0
                            prep_h._retry_count = 0

                    self.state = BotState(stage)
                    self.stage_changed.emit(stage)
                    #self.log_message.emit('ok', 'Stage: %s -> %s' % (old, stage))

                    if stage == 'gameplay' and old != 'gameplay':
                        gameplay_h = self._handlers.get('gameplay')
                        if gameplay_h:
                            gameplay_h.reset()

                    if stage == 'prep' and old in ('results', 'lobby', 'idle'):
                        prep_h = self._handlers.get('prep')
                        if prep_h:
                            prep_h._fast_step = 0
                            prep_h._relay_step = 0
                            prep_h._boost_step = 0
                            prep_h._retry_count = 0

                if stage in self._handlers:
                    self._handlers[stage].run(screenshot, view_w, view_h)

                time.sleep(self._loop_interval)

            except Exception:
                self.log_message.emit('err', traceback.format_exc())
                time.sleep(1)

        self.log_message.emit('warn', 'Bot stopped')
        self.bot_finished.emit()

    def _run_gitbox_mode(self):
        handler = self._handlers.get('gitbox')
        if not handler:
            self.log_message.emit('err', 'Gitbox handler not found')
            self.bot_finished.emit()
            return

        #self.log_message.emit('ok', 'Gitbox mode: กำลังเปิดกล่อง...')

        while not self._stop_flag:
            if not self.app.emulator.connected:
                self.log_message.emit('warn', 'Emulator disconnected, waiting...')
                time.sleep(2)
                continue

            try:
                screenshot = self.app.emulator.screenshot()
                if screenshot is None:
                    time.sleep(1)
                    continue

                size = self.app.emulator.get_size()
                if not size:
                    time.sleep(1)
                    continue

                view_w, view_h = size
                handler.run(screenshot, view_w, view_h)

                time.sleep(self._loop_interval)

            except Exception:
                self.log_message.emit('err', traceback.format_exc())
                time.sleep(1)

        #self.log_message.emit('warn', 'Gitbox mode stopped')
        self.bot_finished.emit()

    def stop(self):
        self._stop_flag = True

    def on_settings_updated(self):
        """Called when settings are saved while bot is running."""
        new_mode = self.app.config.settings.get('farm_mode', self.farm_mode)
        if new_mode != self.farm_mode:
            self.farm_mode = new_mode

    def reset(self):
        self.state = BotState.IDLE
        self._state_unseen_since = None
        self._runs = 0
        self._handlers.clear()
        self._loop_interval = 0.3

    def _init_handlers(self):
        from game.launch import LaunchHandler
        from game.lobby import LobbyHandler
        from game.prep import PrepHandler
        from game.gameplay import GameplayHandler
        from game.results import ResultsHandler
        from game.gitbox.handler import GitboxHandler

        self._handlers = {
            'launch': LaunchHandler(self),
            'lobby': LobbyHandler(self),
            'prep': PrepHandler(self),
            'gameplay': GameplayHandler(self),
            'results': ResultsHandler(self),
            'gitbox': GitboxHandler(self),
        }

    def _detect_stage(self, screenshot, view_w, view_h):
        current = self.state.value
        # Verify the presumed state first. If it no longer matches, scan every
        # known state instead of indefinitely retaining an outdated state.
        current_handler = self._handlers.get(current)
        current_check = getattr(current_handler, '_check_%s' % current, None)
        if current_check and current_check(screenshot, view_w, view_h):
            self._state_unseen_since = None
            return current

        detected = self._scan_all_stages(screenshot, view_w, view_h)
        if detected:
            self._state_unseen_since = None
            return detected

        # If state cannot be detected, reset to IDLE and let the next loop
        # acquire Lobby (or another known state) again.
        now = time.monotonic()
        if self._state_unseen_since is None:
            self._state_unseen_since = now
        elif now - self._state_unseen_since >= _STATE_RECOVERY_TIMEOUT:
            self._state_unseen_since = None
            return BotState.IDLE.value

        return current

    def _scan_all_stages(self, screenshot, view_w, view_h):
        """Return the visible known stage, or None if the screen is unknown."""
        # Results first prevents an end dialog from being mistaken for the
        # underlying lobby; Lobby is checked before Gameplay.
        for stage_name in ['results', 'prep', 'lobby', 'gameplay', 'launch']:
            handler = self._handlers.get(stage_name)
            if handler is None:
                continue
            check_method = getattr(handler, '_check_%s' % stage_name, None)
            if check_method and check_method(screenshot, view_w, view_h):
                return stage_name
        return None

