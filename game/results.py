"""game/results.py -- Results stage handler."""
import time
import logging

from vision.engine import VisionEngine

log = logging.getLogger(__name__)


class ResultsHandler:
    """Handles results screen: level up, OK, confirm, open boxes."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()

    def run(self, screenshot, view_w, view_h):
        checks = [
            ('Template Level up', lambda: self._tap_retry('Level Up Confirm')),
            ('OK',                lambda: self._tap_retry('OK')),
            ('Confirm',           lambda: self._tap_retry('Confirm')),
            ('Open All',          lambda: self._tap_retry('Open All')),
            ('Overtake OK',          lambda: self._tap_retry('Overtake OK')),
        ]
        for point_name, action in checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                action()
                return

    def _detect(self, screenshot, view_w, view_h, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('results')
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                result = self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, 'results')
                return result
        return None

    def _check_results(self, screenshot, view_w, view_h):
        """Check if on results screen (Open All, Confirm, OK, Level Up)."""
        for name in ['Open All', 'Confirm', 'OK', 'Template Level up','Overtake OK']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                return True
        return False

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('results')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(
                    p[1], p[2], box_w_pct=p[3], box_h_pct=p[4])
                time.sleep(0.3)
                return True
        return False

    def _tap_retry(self, point_name, retries=2, delay=0.4):
        """Tap once; the next loop confirms whether the result advanced."""
        return self._tap(point_name)
