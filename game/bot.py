"""game/bot.py -- Bot worker thread."""
import time
import logging
import traceback
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from game.state import BotState
from vision.engine import VisionEngine

log = logging.getLogger(__name__)


# A missing template for one frame is normal. This only recovers from an
# unrecognised screen that persists for several seconds.
_STATE_RECOVERY_TIMEOUT = 8.0
_MAX_CONSECUTIVE_RECOVERIES = 3


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
        self._recovery_count = 0

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
        self._recovery_count = 0
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
            self._recovery_count = 0
            return current

        detected = self._scan_all_stages(screenshot, view_w, view_h)
        if detected:
            self._state_unseen_since = None
            self._recovery_count = 0
            return detected

        # Allow transient loading/animation frames. If no known state has
        # appeared for too long, return to idle so the next loop acquires Lobby
        # (or another known state) again.
        now = time.monotonic()
        if self._state_unseen_since is None:
            self._state_unseen_since = now
        elif now - self._state_unseen_since >= _STATE_RECOVERY_TIMEOUT:
            self._recovery_count += 1
            image_path = self._save_recovery_screenshot(
                screenshot, current, self._recovery_count)
            self.log_message.emit(
                'warn',
                'State %s not detected for %.0fs; recovery #%d%s' %
                (current, now - self._state_unseen_since,
                 self._recovery_count,
                 ' (saved: %s)' % image_path if image_path else ''))
            if self._recovery_count >= _MAX_CONSECUTIVE_RECOVERIES:
                self.log_message.emit(
                    'err',
                    'Screen remains unknown after %d recoveries; check the '
                    'emulator window and the saved recovery screenshots.' %
                    self._recovery_count)
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

    @staticmethod
    def _save_recovery_screenshot(screenshot, state, recovery_count):
        """Save evidence only when recovery fires, never on normal loops."""
        try:
            folder = Path(__file__).resolve().parents[1] / 'debug' / 'recovery'
            folder.mkdir(parents=True, exist_ok=True)
            filename = 'unknown_%s_%s_%d.png' % (
                state, time.strftime('%Y%m%d_%H%M%S'), recovery_count)
            path = folder / filename
            screenshot.save(path)
            return str(path)
        except Exception as exc:
            log.warning('Could not save recovery screenshot: %s', exc)
            return None

