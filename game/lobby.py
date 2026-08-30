"""game/lobby.py -- Lobby stage handler."""
import time
from vision.engine import VisionEngine
import random


class LobbyHandler:
    """Handles lobby screen: clear popups and press Play."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._relic_step = 0
        self._relic_deadline = 0.0
        self._relic_confirm_count = 0

    def run(self, screenshot, view_w, view_h):
        # 1. Dismiss unrelated popups first. Tap and continue (don't abort frame).
        popup_checks = [
            # The Congratulations dialog uses this exact template and frame.
            # Check it first: other generic Confirm templates can also match
            # this button, but have different configured coordinates.
            ('Confirm Relic', lambda: self._tap_template_or_coord('Confirm Relic')),
            ('Close Relic', lambda: self._tap_template_or_coord('Close Relic')),
            ('League Confirm', lambda: self._tap_template_or_coord('League Confirm')),
            # Congratulations uses the Confirm Relic button coordinates.
            ('Close News',    lambda: self._tap_template_or_coord('Close News')),
            ('Daily OK',      lambda: self._tap_template_or_coord('Daily OK')),
            ('Lobby Ok',      lambda: self._tap_nosleep('Lobby Ok')),
            ('Lobby Confrim', lambda: self._tap_nosleep('Lobby Confrim')),
        ]
        for point_name, action in popup_checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                self._log(f"Popup detected: {point_name}")
                try:
                    tapped = action()
                except Exception as e:
                    tapped = False
                    self._log(f"Error tapping popup {point_name}: {e}")
                if tapped:
                    self._log(f"Tapped popup: {point_name}")
                else:
                    self._log(f"Failed to tap popup: {point_name}")
                # Wait for a fresh screenshot after a popup tap. Continuing in
                # this frame can click the dialog underneath with stale pixels.
                return

        # 2. Relic: Got! -> Relic click -> Claim -> Confirm -> Close.
        if self.app.config.settings.get('relic_check', True):
            if self._run_relic_flow(screenshot, view_w, view_h):
                return

        # 3. Play Button
        result = self._detect(screenshot, view_w, view_h, 'Play Button')
        if result and result.get('found'):
            self._tap_retry('Play Button')
            
    def _run_relic_flow(self, screenshot, view_w, view_h):
        """Simplified relic flow (no experimental fallbacks).

        Steps:
        0) If Relic Diamond OCR contains 'got', tap 'Relic click' -> step 1
        1) If 'Clam Relic' or 'Claim Relic' detected, tap and go to step 2
        2) If 'Confirm Relic' detected, tap once (count toward 5) -> step 3 when reached
        3) If 'Close Relic' detected, tap and reset
        """
        self._log(f"_run_relic_flow: step={self._relic_step} confirm_count={self._relic_confirm_count}")

        if self._relic_step and time.monotonic() > self._relic_deadline:
            self._log("Relic flow deadline exceeded; resetting")
            self._reset_relic_flow()
            return False

        # Step 0
        if self._relic_step == 0:
            diamond = self._detect(screenshot, view_w, view_h, 'Relic Diamond')
            diamond_text = (diamond or {}).get('text', '') or ''
            if diamond and diamond.get('found') and 'got' in diamond_text.lower():
                self._log("Got found in diamond text; tapping Relic click")
                if self._tap_template_or_coord('Relic click'):
                    self._set_relic_step(1)
                return True
            return False

        # Step 1
        if self._relic_step == 1:
            for name in ('Clam Relic', 'Claim Relic'):
                found = self._detect(screenshot, view_w, view_h, name)
                if found and found.get('found'):
                    self._log(f"Detected claim '{name}'; tapping")
                    tapped = self._tap_template_or_coord(name)
                    if not tapped:
                        pct_x = found.get('pct_x')
                        pct_y = found.get('pct_y')
                        if pct_x is not None and pct_y is not None:
                            tapped = self._do_tap(pct_x, pct_y)
                    if tapped:
                        self._set_relic_step(2)
                    return True
            return True

        # Step 2
        if self._relic_step == 2:
            confirm = self._detect(screenshot, view_w, view_h, 'Confirm Relic')
            if confirm and confirm.get('found'):
                self._log("Confirm visible; tapping once")
                tapped = self._tap_template_or_coord('Confirm Relic')
                if not tapped:
                    pct_x = confirm.get('pct_x')
                    pct_y = confirm.get('pct_y')
                    if pct_x is not None and pct_y is not None:
                        tapped = self._do_tap(pct_x, pct_y)
                if tapped:
                    self._relic_confirm_count += 1
                    self._relic_deadline = time.monotonic() + 5.0
                    self._log(f"Confirm tap registered (count={self._relic_confirm_count})")
                else:
                    self._log("Confirm visible but tap failed")
            return True

        # Step 3
        if self._relic_step == 3:
            close = self._detect(screenshot, view_w, view_h, 'Close Relic')
            if close and close.get('found'):
                self._log("Detected Close Relic; tapping")
                if self._tap_template_or_coord('Close Relic'):
                    self._reset_relic_flow()
                else:
                    self._log("Close Relic detected but tap failed")
            return True

        # default
        self._reset_relic_flow()
        return False

    def _set_relic_step(self, step):
        """Advance the relic flow and give the next screen time to appear."""
        self._relic_step = step
        self._relic_deadline = time.monotonic() + 5.0
        if step != 2:
            self._relic_confirm_count = 0

    def _reset_relic_flow(self):
        """Return relic handling to its initial state after close/timeout."""
        self._relic_step = 0
        self._relic_deadline = 0.0
        self._relic_confirm_count = 0

    def _log(self, msg):
        logger = getattr(self.app, 'logger', None)
        if logger and hasattr(logger, 'info'):
            logger.info(f"[LobbyHandler] {msg}")
        else:
            print(f"[LobbyHandler] {msg}")


    def _do_tap(self, x, y, jitter=0.03, box_w_pct=None, box_h_pct=None):
        """Tap a coordinate; framed points are randomised by TapEngine only."""
        try:
            try:
                xf = float(x)
                yf = float(y)
            except Exception:
                return False

            if box_w_pct and box_h_pct:
                # Config coordinates are already percentage values (0..100).
                # Do not add this handler's legacy jitter: it would shift the
                # ROI itself and let a click escape its configured frame.
                tx, ty = xf, yf
            elif 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
                # percentage coords: apply fractional jitter
                dx = random.uniform(-jitter, jitter)
                dy = random.uniform(-jitter, jitter)
                tx = max(0.0, min(1.0, xf + dx))
                ty = max(0.0, min(1.0, yf + dy))
            else:
                # pixel coords: jitter by a few pixels so taps vary
                dx = random.uniform(-10, 10)
                dy = random.uniform(-10, 10)
                tx = xf + dx
                ty = yf + dy

            self.app.emulator.tap(
                tx, ty, box_w_pct=box_w_pct, box_h_pct=box_h_pct)
            # small random post-tap delay to vary timing
            time.sleep(random.uniform(0.03, 0.12))
            return True
        except Exception as e:
            self._log(f"_do_tap error tapping ({x},{y}): {e}")
            return False

    def _detect(self, screenshot, view_w, view_h, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                return self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, 'lobby')

        # Fallback to template search
        res = self.engine.find_template(screenshot, point_name, stage='lobby', threshold=0.72)
        if res and res.get('found'):
            return res
        return None

    def _tap_template_or_coord(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                if self._do_tap(p[1], p[2], box_w_pct=p[3], box_h_pct=p[4]):
                    return True
                return False

        # Check template location
        res = self.engine.find_template(self.app.emulator.screenshot(), point_name, stage='lobby', threshold=0.72)
        if res and res.get('found'):
            pct_x = res.get('pct_x')
            pct_y = res.get('pct_y')
            if pct_x is not None and pct_y is not None:
                return self._do_tap(pct_x, pct_y)
        return False

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                if self._do_tap(p[1], p[2], box_w_pct=p[3], box_h_pct=p[4]):
                    time.sleep(0.3)
                    return True
                return False
        return False

    def _tap_retry(self, point_name, retries=2, delay=0.4):
        """Tap once; only a fresh frame may justify another tap."""
        return self._tap(point_name)

    def _tap_nosleep(self, point_name):
        self._log(f"_tap_nosleep: trying {point_name}")
        # Try coords or template fallback via _tap_template_or_coord
        tapped = self._tap_template_or_coord(point_name)
        if tapped:
            self._log(f"_tap_nosleep: tapped {point_name}")
            return True
        self._log(f"_tap_nosleep: failed to tap {point_name}")
        return False

    def _check_lobby(self, screenshot, view_w, view_h):
        """Check if on lobby screen."""
        for name in ['Play Button', 'Close News', 'Daily OK', 'Daily Confirm',
                     'League Confirm', 'Lobby Ok', 'Lobby Confrim','Confirm Relic','Claim Relic','Close Relic','relic_check']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                return True
        return False
