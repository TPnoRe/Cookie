"""game/launch.py -- Game Launch and Intro Popup stage handler."""
import time
import logging

from vision.engine import VisionEngine

log = logging.getLogger(__name__)


class LaunchHandler:
    """Handles game startup: launch app from home screen and clear intro popups."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._last_launch_tap = 0
        self._last_loading_log = 0

    def reset(self):
        self._last_launch_tap = 0
        self._last_loading_log = 0

    def run(self, screenshot, view_w, view_h):
        now = time.time()

        # ── 1. ตรวจจับและปิดป๊อปอัพตอนเข้าเกม ───────────────────────────
        # ป๊อปอัพแสดงความยินดี Congratulations ([Confirm] center) — ตรวจสอบก่อนเพื่อปิด Modal ด้านหน้า
        res_congrats = self._detect_template(screenshot, view_w, view_h, 'Daily Confirm', 'lobby', threshold=0.72)
        if not (res_congrats and res_congrats.get('found')):
            res_congrats = self._detect_roi_or_ocr(screenshot, view_w, view_h, 'Daliy Confirm')
        if res_congrats and res_congrats.get('found'):
            self._tap_result(res_congrats, 'Daily Confirm')
            time.sleep(0.5)
            return

        # ป๊อปอัพข่าวสาร News ([X] top right)
        res_news = self._detect_template(screenshot, view_w, view_h, 'Close News', 'lobby', threshold=0.72)
        if not (res_news and res_news.get('found')):
            res_news = self._detect_template(screenshot, view_w, view_h, 'Close Event', 'lobby', threshold=0.72)
        if res_news and res_news.get('found'):
            self._tap_result(res_news, 'Close News')
            time.sleep(0.5)
            return

        # ป๊อปอัพเช็คชื่อ Daily Check-in ([OK] bottom)
        res_daily_ok = self._detect_template(screenshot, view_w, view_h, 'Daily OK', 'lobby', threshold=0.72)
        if not (res_daily_ok and res_daily_ok.get('found')):
            res_daily_ok = self._detect_roi_or_ocr(screenshot, view_w, view_h, 'Lobby Ok')
        if res_daily_ok and res_daily_ok.get('found'):
            self._tap_result(res_daily_ok, 'Daily OK')
            time.sleep(0.5)
            return

        # ป๊อปอัพทั่วไป (Close Relic / Lobby Confrim / Claim Relic / Confirm Relic)
        for p_name in ['Close Relic', 'Lobby Confrim', 'Claim Relic', 'Confirm Relic']:
            res_popup = self._detect_roi_or_ocr(screenshot, view_w, view_h, p_name)
            if res_popup and res_popup.get('found'):
                self._tap_result(res_popup, p_name)
                time.sleep(0.4)
                return

        # ── 2. ตรวจจับหน้าจอ Home Screen และแตะเปิดเกม ─────────────────
        res_app = self.engine.find_template(screenshot, 'App_Icon', stage='launch', threshold=0.75)
        if res_app and res_app.get('found'):
            if now - self._last_launch_tap > 5.0:
                self._last_launch_tap = now
                click_x = res_app.get('click_x')
                click_y = res_app.get('click_y')
                if click_x is not None and click_y is not None:
                    img_w, img_h = screenshot.size
                    pct_x = (click_x / img_w) * 100.0
                    pct_y = (click_y / img_h) * 100.0
                    self.app.emulator.tap(pct_x, pct_y)
                else:
                    self.app.emulator.tap(50.0, 25.0)
                time.sleep(1.5)
            return

        # ── 3. กำลังโหลดเข้าเกม (Splash Screen / Checking game data) ───
        if now - self._last_loading_log >= 6.0:
            self._last_loading_log = now

    def _check_launch(self, screenshot, view_w, view_h):
        """Check if on home screen or startup popups."""
        # 1. Check App Icon
        res_app = self.engine.find_template(screenshot, 'App_Icon', stage='launch', threshold=0.75)
        if res_app and res_app.get('found'):
            return True

        # 2. Check startup popups (News close, Daily OK, Congrats Confirm)
        for t_name in ['Close News', 'Close Event', 'Daily OK', 'Daily Confirm']:
            res_t = self._detect_template(screenshot, view_w, view_h, t_name, 'lobby', threshold=0.72)
            if res_t and res_t.get('found'):
                return True

        # 3. Check OCR popups
        for p_name in ['Lobby Ok', 'Daliy Confirm', 'Close Relic', 'Lobby Confrim']:
            res_ocr = self._detect_roi_or_ocr(screenshot, view_w, view_h, p_name)
            if res_ocr and res_ocr.get('found'):
                return True

        # 4. If recently launched (within 25s) and not in lobby/gameplay/results
        if time.time() - self._last_launch_tap < 25.0:
            return True

        return False

    def _detect_template(self, screenshot, view_w, view_h, point_name, stage='lobby', threshold=0.72):
        # 1. Try coordinate ROI match first
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                return self.engine.match_template(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, stage=stage, threshold=threshold)

        # 2. Fallback to full screen find_template
        return self.engine.find_template(screenshot, point_name, stage=stage, threshold=threshold)

    def _detect_roi_or_ocr(self, screenshot, view_w, view_h, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                return self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, 'lobby')
        return None

    def _tap_result(self, result, point_name):
        pct_x = result.get('pct_x')
        pct_y = result.get('pct_y')
        if pct_x is not None and pct_y is not None:
            self.app.emulator.tap(pct_x, pct_y)
            return True

        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                return True

        click_x = result.get('click_x')
        click_y = result.get('click_y')
        if click_x is not None and click_y is not None:
            size = self.app.emulator.get_size() or (1280, 720)
            px = (click_x / size[0]) * 100.0
            py = (click_y / size[1]) * 100.0
            self.app.emulator.tap(px, py)
            return True
        return False
