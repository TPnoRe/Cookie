"""game/gitbox/handler.py -- Handler สำหรับ open_gitbox farm mode."""
import time


class GitboxHandler:
    """Handler สำหรับเปิด gitbox - วนลูปจนกว่าจะกดหมด."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self._gitbox_step = 0
        self._last_tap_time = 0
        self._tap_cooldown = 0.8

    def run(self, screenshot, view_w, view_h):
        now = time.time()
        if now - self._last_tap_time < self._tap_cooldown:
            return

        # ลำดับ: Draw → Gitbox → Draw again → Confirm Relic → upgran → วนกลับ
        for name in ['Draw', 'Gitbox ', 'Draw again', 'Confirm Relic', 'upgran', 'Open Gitbox']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                self._tap(name)
                self._last_tap_time = time.time()
                return

    def _detect(self, screenshot, view_w, view_h, name):
        detection_type = self.app.config.get_detection(name)
        coords = self.app.config.get_coords('lobby')
        for c in coords:
            if c[0] == name:
                return self.bot._engine.detect(
                    screenshot, c[1], c[2], c[3], c[4],
                    view_w, view_h, name, detection_type)
        return None

    def _tap(self, point_name):
        coords = self.app.config.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                lc = self.app.emulator.last_click
                if lc:
                    self.bot.log_message.emit(
                        'info', 'Gitbox: tapped %s @ x=%.1f y=%.1f' % (point_name, lc[0], lc[1]))
                return
