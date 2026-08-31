"""game/gameplay.py -- Gameplay stage handler."""
import time
import random

from vision.engine import VisionEngine


class GameplayHandler:
    """Handles gameplay: fast start, jump, cookie relay."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._last_jump_time = 0
        self._entry_jump_tap_count = 0
        self._fast_start_handled = False
        self._relay_handled = False

    def reset(self):
        """Reset per-run gameplay state when entering gameplay."""
        self._last_jump_time = 0
        self._entry_jump_tap_count = 0
        self._fast_start_handled = False
        self._relay_handled = False

    def _get_setting(self, key, default):
        return self.app.config.settings.get(key, default)

    def run(self, screenshot, view_w, view_h):
        farm_mode = self._get_setting('farm_mode', self.bot.farm_mode)
        jump_enabled = farm_mode in ('farm_gold', 'farm_exp')
        jump_interval = float(self._get_setting('jump_interval', '0.8'))
        cookie_relay_enabled = bool(self._get_setting('cookie_relay', True))
        fast_start_enabled = bool(self._get_setting('fast_start', True))
        fast_start_delay = float(self._get_setting('fast_start_delay', '1.0'))

        # farm_box: when Jump first appears in a run, tap it quickly.
        # reset() clears this marker when the bot enters the next gameplay run.
        if farm_mode == 'farm_box' and self._entry_jump_tap_count == 0:
            result = self._detect(screenshot, view_w, view_h, 'Fast Start')
            jump = self._detect(screenshot, view_w, view_h, 'Jump')
            if (jump and jump.get('found')) or (result and result.get('found')):
                taps = random.randint(2, 4)
                self.bot.log_message.emit(
                    'ok', f'farm_box: พบ Fast Start → กด Jump {taps} ครั้ง (delay=0.05)')
                for _ in range(taps):
                    self._tap('Jump')
                    time.sleep(0.05)
                self._entry_jump_tap_count = 1
            return

        # Priority 1: Fast Start (อันดับ 1 ตามสเปค)
        if fast_start_enabled and not self._fast_start_handled:
            result = self._detect(screenshot, view_w, view_h, 'Fast Start')
            if result and result.get('found'):
                if fast_start_delay > 0:
                    time.sleep(fast_start_delay)
                self._fast_start_handled = self._tap('Fast Start')
                return

        # Priority 2: Cookie Relay (อันดับ 2)
        if cookie_relay_enabled and not self._relay_handled:
            result = self._detect(screenshot, view_w, view_h, 'Cookie Relay')
            if result and result.get('found'):
                for _ in range(5):
                    self._tap('Cookie Relay')
                    time.sleep(0.1)
                self._relay_handled = True
                return

        # farm_gold / farm_exp: use the configured interval between actions.
        # Each action is randomly a single jump or a double jump.
        if jump_enabled:
            now_monotonic = time.monotonic()
            if now_monotonic - self._last_jump_time >= jump_interval:
                jump = self._detect(screenshot, view_w, view_h, 'Jump')
                if jump and jump.get('found'):
                    if random.choice((True, False)):
                        self._single_jump()
                    else:
                        self._double_jump()
                    # Set this after the action, ensuring double jump's second
                    # tap cannot be followed by an early next action.
                    self._last_jump_time = time.monotonic()
            return


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

    def _do_tap(self, x, y, box_w_pct=None, box_h_pct=None, jitter=0.03):
        """Tap with jitter for gameplay taps. x,y are pct coords (0..1) or pixels.
        If box widths/heights are provided, pass them along to tap/tap_fast.
        """
        try:
            xf = float(x)
            yf = float(y)
        except Exception:
            return False
        # pct coords
        if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
            dx = random.uniform(-jitter, jitter)
            dy = random.uniform(-jitter, jitter)
            tx = max(0.0, min(1.0, xf + dx))
            ty = max(0.0, min(1.0, yf + dy))
        else:
            dx = random.uniform(-10, 10)
            dy = random.uniform(-10, 10)
            tx = xf + dx
            ty = yf + dy
        try:
            if box_w_pct is not None and box_h_pct is not None:
                # Use tap_fast when box provided (keeps behavior for Fast Start/Cookie Relay)
                self.app.emulator.tap_fast(tx, ty, box_w_pct, box_h_pct)
            else:
                # generic tap
                self.app.emulator.tap(tx, ty)
            # small random sleep to vary timing
            time.sleep(random.uniform(0.02, 0.08))
            return True
        except Exception:
            return False

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('gameplay')
        for p in coords:
            if p[0] == point_name:
                # p layout: (name, x, y, box_w_pct, box_h_pct)
                if point_name in ('Cookie Relay', 'Fast Start'):
                    # use tap_fast with jitter
                    return self._do_tap(p[1], p[2], box_w_pct=p[3], box_h_pct=p[4])
                else:
                    return self._do_tap(p[1], p[2], box_w_pct=p[3], box_h_pct=p[4])
        return False

    def _single_jump(self):
        self._tap('Jump')

    def _double_jump(self):
        self._tap('Jump')
        time.sleep(0.05)
        self._tap('Jump')
