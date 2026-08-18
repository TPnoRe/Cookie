"""game/bot.py -- Bot worker thread."""
import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from game.state import BotState
from vision.engine import VisionEngine

log = logging.getLogger(__name__)


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
        self._force_until = 0

    def run(self):
        self.log_message.emit('ok', 'Bot started (%s)' % self.farm_mode)
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
                        self.log_message.emit(
                            'ok', 'Results: run #%d completed!' % self._runs)
                        prep_h = self._handlers.get('prep')
                        if prep_h:
                            prep_h._relay_step = 0
                            prep_h._boost_step = 0
                            prep_h._multi_buy_clicked = False

                    self.state = BotState(stage)
                    self.stage_changed.emit(stage)
                    self.log_message.emit('info', 'Stage: %s -> %s' % (old, stage))

                    if stage == 'prep':
                        prep_h = self._handlers.get('prep')
                        if prep_h:
                            prep_h._relay_step = 0
                            prep_h._boost_step = 0
                            prep_h._multi_buy_clicked = False

                if stage in self._handlers:
                    self._handlers[stage].run(screenshot, view_w, view_h)

                time.sleep(self._loop_interval)

            except Exception as e:
                self.log_message.emit('err', 'Bot error: %s' % str(e))
                time.sleep(1)

        self.log_message.emit('warn', 'Bot stopped')
        self.bot_finished.emit()

    def _run_gitbox_mode(self):
        handler = self._handlers.get('gitbox')
        if not handler:
            self.log_message.emit('err', 'Gitbox handler not found')
            self.bot_finished.emit()
            return

        self.log_message.emit('ok', 'Gitbox mode: กำลังเปิดกล่อง...')

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

            except Exception as e:
                self.log_message.emit('err', 'Gitbox error: %s' % str(e))
                time.sleep(1)

        self.log_message.emit('warn', 'Gitbox mode stopped')
        self.bot_finished.emit()

    def stop(self):
        self._stop_flag = True

    def reset(self):
        self.state = BotState.IDLE
        self._force_until = 0
        self._runs = 0
        self._handlers.clear()
        self._loop_interval = 0.3

    def _init_handlers(self):
        from game.lobby import LobbyHandler
        from game.prep import PrepHandler
        from game.gameplay import GameplayHandler
        from game.results import ResultsHandler
        from game.gitbox.handler import GitboxHandler

        self._handlers = {
            'lobby': LobbyHandler(self),
            'prep': PrepHandler(self),
            'gameplay': GameplayHandler(self),
            'results': ResultsHandler(self),
            'gitbox': GitboxHandler(self),
        }

    def _detect_stage(self, screenshot, view_w, view_h):
        if time.time() < self._force_until:
            return self.state.value

        current = self.state.value

        if current == 'gameplay':
            if self._handlers['gameplay']._check_gameplay(screenshot, view_w, view_h):
                return 'gameplay'
            if self._handlers['results']._check_results(screenshot, view_w, view_h):
                return 'results'
            # fallback: ตรวจทุก state
            for stage_name in ['results', 'prep', 'lobby']:
                check = getattr(self._handlers.get(stage_name), '_check_%s' % stage_name, None)
                if check and check(screenshot, view_w, view_h):
                    return stage_name
            return current

        if current == 'results':
            if self._handlers['results']._check_results(screenshot, view_w, view_h):
                return 'results'
            # fallback: ตรวจทุก state
            for stage_name in ['prep', 'lobby', 'gameplay']:
                check = getattr(self._handlers.get(stage_name), '_check_%s' % stage_name, None)
                if check and check(screenshot, view_w, view_h):
                    return stage_name
            return current

        if current == 'prep':
            if self._handlers['prep']._check_prep(screenshot, view_w, view_h):
                return 'prep'
            if self._handlers['gameplay']._check_gameplay(screenshot, view_w, view_h):
                return 'gameplay'
            # fallback: ตรวจทุก state
            for stage_name in ['results', 'lobby']:
                check = getattr(self._handlers.get(stage_name), '_check_%s' % stage_name, None)
                if check and check(screenshot, view_w, view_h):
                    return stage_name
            return current

        # idle/lobby → ตรวจทุกตัว
        for stage_name in ['results', 'prep', 'lobby', 'gameplay']:
            handler = self._handlers.get(stage_name)
            if handler is None:
                continue
            check_method = getattr(handler, '_check_%s' % stage_name, None)
            if check_method and check_method(screenshot, view_w, view_h):
                return stage_name

        return current
