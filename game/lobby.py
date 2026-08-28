"""game/lobby.py -- Lobby stage handler."""
import time
import logging

from vision.engine import VisionEngine

log = logging.getLogger(__name__)


class LobbyHandler:
    """Handles lobby screen: clear popups, claim relics, press Play."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()

    def run(self, screenshot, view_w, view_h):
        # 1. Dismiss popups ก่อน (League Confirm / Daily Confirm / Close News / Daily OK / Lobby Ok / Lobby Confrim / Close Relic)
        popup_checks = [
            ('League Confirm', lambda: self._tap_template_or_coord('League Confirm')),
            ('Daily Confirm', lambda: self._tap_template_or_coord('Daily Confirm')),
            ('Close News',    lambda: self._tap_template_or_coord('Close News')),
            ('Close Event',   lambda: self._tap_template_or_coord('Close Event')),
            ('Daily OK',      lambda: self._tap_template_or_coord('Daily OK')),
            ('Lobby Ok',      lambda: self._tap_nosleep('Lobby Ok')),
            ('Lobby Confrim', lambda: self._tap_nosleep('Lobby Confrim')),
            ('Close Relic',   lambda: self._tap_nosleep('Close Relic')),
        ]
        for point_name, action in popup_checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                action()
                return

        # 2. Relic claims
        relic_check_enabled = self.app.config.settings.get('relic_check', True)
        if relic_check_enabled:
            relic_checks = [
                ('Claim Relic',    lambda: self._tap_nosleep('Claim Relic')),
                ('Confirm Relic',  lambda: self._tap_nosleep('Confirm Relic')),
                ('Close Relic',    lambda: self._tap_nosleep('Close Relic')),
            ]
            for point_name, action in relic_checks:
                result = self._detect(screenshot, view_w, view_h, point_name)
                if result and result.get('found'):
                    action()
                    time.sleep(0.3)
                    return

        # 3. Play Button
        result = self._detect(screenshot, view_w, view_h, 'Play Button')
        if result and result.get('found'):
            self._tap_retry('Play Button')

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
                self.app.emulator.tap(p[1], p[2])
                return True

        # Check template location
        res = self.engine.find_template(self.app.emulator.screenshot(), point_name, stage='lobby', threshold=0.72)
        if res and res.get('found'):
            pct_x = res.get('pct_x')
            pct_y = res.get('pct_y')
            if pct_x is not None and pct_y is not None:
                self.app.emulator.tap(pct_x, pct_y)
                return True
        return False

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                time.sleep(0.3)
                return True
        return False

    def _tap_retry(self, point_name, retries=2, delay=0.4):
        for i in range(retries + 1):
            if self._tap(point_name):
                return True
            if i < retries:
                time.sleep(delay)
        return False

    def _tap_nosleep(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                return True
        return False

    def _check_lobby(self, screenshot, view_w, view_h):
        """Check if on lobby screen."""
        for name in ['Play Button', 'Relic Diamond', 'Close News', 'Daily OK', 'Daily Confirm',
                     'League Confirm', 'Claim Relic', 'Close Relic', 'Confirm Relic',
                     'Lobby Ok', 'Lobby Confrim']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                return True
        return False

