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
        # Relic flow: one step per bot loop (ตรวจสอบด้วย screenshot จริงทุกรอบ)
        relic_checks = [
            #('Relic Diamond',  lambda: self._tap_nosleep('Relic Diamond')),
            #('Claim Relic',    lambda: self._tap_nosleep('Claim Relic')),
            #('Confirm Relic',  lambda: self._tap_nosleep('Confirm Relic')),
            ('Lobby Ok',       lambda: self._tap_nosleep('Lobby Ok')),
            ('Close Relic',    lambda: self._tap_nosleep('Close Relic')),
        ]
        for point_name, action in relic_checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                action()
                #self.bot.log_message.emit('info', 'Lobby: tapped %s' % point_name)
                time.sleep(0.3)
                return

        # Dismiss popups ก่อน (OK / Confirm / Close)
        popup_checks = [
            ('OK',      lambda: self._tap('OK')),
            ('Confirm', lambda: self._tap('Confirm')),
            ('Close',   lambda: self._tap('Close')),         
        ]
        for point_name, action in popup_checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                action()
                return
                
        event_checks = [
            ('Confrim Event', lambda: self._tap_nosleep('Confrim Event')),
            ('Claim Event',      lambda: self._tap_nosleep('Claim Event')),
            ('Close Event',   lambda: self._tap_nosleep('Close Event')),            
        ]
        for point_name, action in event_checks:
            result = self._detect(screenshot, view_w, view_h, point_name)
            if result and result.get('found'):
                action()
                return
            
        # กดเล่นก็ต่อเมื่อเห็น Play Button จริงๆ
        # ไม่บังคับ state — ปล่อยให้ bot loop ตรวจสอบ stage ใหม่เอง
        result = self._detect(screenshot, view_w, view_h, 'Play Button')
        if result and result.get('found'):
            self._tap('Play Button')
            #self.bot.log_message.emit('info', 'Lobby: pressed Play Button')

    def _detect(self, screenshot, view_w, view_h, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                result = self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, 'lobby')
                return result
        return None

    def _tap(self, point_name):
        cfg = self.app.config
        coords = cfg.get_coords('lobby')
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                lc = self.app.emulator.last_click
                #if lc:
                    #self.bot.log_message.emit('info', 'Lobby: tapped %s @ x=%.1f y=%.1f' % (point_name, lc[0], lc[1]))
                time.sleep(0.3)
                return True
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
        for name in ['Play Button', 'Relic Diamond',
                     'Claim Relic', 'Close Relic', 'Confirm Relic', 'Lobby Ok','Confirm  Event','Claim Event','Close Event']:
            result = self._detect(screenshot, view_w, view_h, name)
            if result and result.get('found'):
                return True
        return False
