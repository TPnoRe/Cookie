"""game/gitbox/handler.py -- Handler สำหรับ open_gitbox farm mode."""
import time


class GitboxHandler:
    """Handler สำหรับเปิด gitbox - วนลูปจนกว่าจะกดหมด."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self._last_tap_time = 0
        self._tap_cooldown = 0.5

    def run(self, screenshot, view_w, view_h):
        now = time.time()
        if now - self._last_tap_time < self._tap_cooldown:
            return

        # 1. Dismiss popups ก่อน (สำคัญมาก!)
        for name in ['Lobby Ok', 'Close Relic', 'Close Event',
                     'Confirm  Event', 'Claim Event',
                     'OK', 'Confirm', 'Close']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                self._tap_retry(name)
                self._last_tap_time = time.time()
                return

        # 2. หา Open Gitbox (กดเข้าหน้า gitbox)
        result = self._detect(screenshot, view_w, view_h, 'Open Gitbox')
        if result and result.get('found'):
            self._tap_retry('Open Gitbox')
            self._last_tap_time = time.time()
            return

        # 3. Gitbox flow: Draw → Gitbox → Draw again → Confirm Relic → upgran
        for name in ['Draw', 'Gitbox ', 'Draw again', 'Confirm Relic', 'upgran']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                self._tap_retry(name)
                self._last_tap_time = time.time()
                return

    def _detect(self, screenshot, view_w, view_h, name):
        detection_type = self.app.config.get_detection(name)
        for stage in ['lobby', 'prep', 'results', 'gameplay']:
            coords = self.app.config.get_coords(stage)
            for c in coords:
                if c[0] == name:
                    return self.bot._engine.detect(
                        screenshot, c[1], c[2], c[3], c[4],
                        view_w, view_h, name, detection_type)
        return None

    def _tap(self, point_name):
        for stage in ['lobby', 'prep', 'results', 'gameplay']:
            coords = self.app.config.get_coords(stage)
            for p in coords:
                if p[0] == point_name:
                    self.app.emulator.tap(p[1], p[2])
                    return True
        return False

    def _tap_retry(self, point_name, retries=2, delay=0.4):
        for i in range(retries + 1):
            if self._tap(point_name):
                return True
            if i < retries:
                time.sleep(delay)
        return False
