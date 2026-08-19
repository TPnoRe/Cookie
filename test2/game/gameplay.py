"""game/gameplay.py -- Gameplay stage handler."""
import time
import random
import logging

from vision.engine import VisionEngine

log = logging.getLogger(__name__)


class GameplayHandler:
    """Handles gameplay: fast start, jump, cookie relay."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._last_jump_time = 0

    def _get_setting(self, key, default):
        return self.app.config.settings.get(key, default)

    def run(self, screenshot, view_w, view_h):
        farm_mode = self._get_setting('farm_mode', self.bot.farm_mode)
        jump_enabled = farm_mode in ('farm_gold', 'farm_exp')
        jump_interval = float(self._get_setting('jump_interval', '0.8'))
        cookie_relay_enabled = bool(self._get_setting('cookie_relay', True))
        fast_start_enabled = bool(self._get_setting('fast_start', True))
        fast_start_delay = float(self._get_setting('fast_start_delay', '1.0'))

        # Priority 1: Cookie Relay
        if cookie_relay_enabled:
            result = self._detect(screenshot, view_w, view_h, 'Cookie Relay')
            if result and result.get('found'):
                for _ in range(5):
                    self._tap('Cookie Relay')
                    time.sleep(0.1)
                return

        # Priority 2: Fast Start (if enabled)
        if fast_start_enabled:
            result = self._detect(screenshot, view_w, view_h, 'Fast Start')
            if result and result.get('found'):
                time.sleep(fast_start_delay)
                self._tap('Fast Start')
                return

        # Priority 3: Jump (if enabled)
        if jump_enabled:
            now = time.time()
            if now - self._last_jump_time >= jump_interval:
                if self._detect_pit(screenshot, view_w, view_h):
                    self._double_jump()
                else:
                    action = random.choice(['jump', 'double_jump'])
                    if action == 'jump':
                        self._single_jump()
                    else:
                        self._double_jump()
                self._last_jump_time = now

    def _detect(self, screenshot, view_w, view_h, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('gameplay')
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                result = self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, 'gameplay')
                return result
        return None

    def _check_gameplay(self, screenshot, view_w, view_h):
        """Check if on gameplay screen (Jump or Slide)."""
        result = self._detect(screenshot, view_w, view_h, 'Jump')
        if result and result.get('found'):
            return True
        result = self._detect(screenshot, view_w, view_h, 'Slide')
        if result and result.get('found'):
            return True
        return False

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('gameplay')
        for p in coords:
            if p[0] == point_name:
                if point_name in ('Cookie Relay', 'Fast Start'):
                    self.app.emulator.tap_fast(p[1], p[2])
                else:
                    self.app.emulator.tap(p[1], p[2])
                lc = self.app.emulator.last_click
                if lc:
                    self.bot.log_message.emit(
                        'info', 'Gameplay: tapped %s @ x=%.1f y=%.1f'
                        % (point_name, lc[0], lc[1]))
                return True
        return False

    def _detect_pit(self, screenshot, view_w, view_h):
        try:
            import cv2
            import numpy as np
            from emulator.coords import scale_rect

            rx, ry, rw, rh = scale_rect(
                view_w, view_h, 36.0, 65.0, 2.0, 2.0)
            img_w, img_h = screenshot.size
            x1 = max(0, min(rx, img_w - 1))
            y1 = max(0, min(ry, img_h - 1))
            x2 = min(img_w, x1 + max(1, rw))
            y2 = min(img_h, y1 + max(1, rh))

            if x2 <= x1 or y2 <= y1:
                return False

            roi = screenshot.crop((x1, y1, x2, y2))
            roi_np = np.array(roi)
            avg_color = roi_np.mean(axis=(0, 1))

            return avg_color[0] < 50 and avg_color[1] < 50 and avg_color[2] < 50
        except Exception:
            return False

    def _single_jump(self):
        self._tap('Jump')

    def _double_jump(self):
        self._tap('Jump')
        time.sleep(0.1)
        self._tap('Jump')
