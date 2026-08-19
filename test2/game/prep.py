"""game/prep.py -- Prep stage handler."""
import time
import logging

from vision.engine import VisionEngine
from game.state import BotState

log = logging.getLogger(__name__)


class PrepHandler:
    """Handles prep screen: cookie relay, boost, target buff, start game."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._relay_step = 0   # 0=not started, 1=selected, 2=done
        self._boost_step = 0   # 0=not started, 1=random clicked, 2=in multi tab / waiting buff, 3=done / start game
        self._multi_buy_clicked = False
        self._retry_count = 0
        self._last_roll_time = 0

    def reset(self):
        self._relay_step = 0
        self._boost_step = 0
        self._multi_buy_clicked = False
        self._retry_count = 0
        self._last_roll_time = 0

    def run(self, screenshot, view_w, view_h):
        random_boost_enabled = self.app.config.settings.get('random_boost', True)
        target = self.app.config.settings.get('target_buff', 'Double Coins')

        # ──────────────────────────────────────────────────────
        # 1. Cookie Relay flow (ถ้าเปิดใช้งาน และยังไม่เสร็จ)
        # ──────────────────────────────────────────────────────
        cookie_relay_enabled = self.app.config.settings.get('cookie_relay', True)
        if cookie_relay_enabled and self._relay_step < 2:
            # ถ้าเห็นปุ่ม Buy ให้กดซื้อทันที
            res_buy = self._detect(screenshot, view_w, view_h, 'Buy Cookie Relay', threshold=0.60)
            if res_buy and res_buy.get('found'):
                self.bot.log_message.emit('ok', 'Prep: tapping Buy Cookie Relay')
                self._tap('Buy Cookie Relay')
                self._relay_step = 2
                time.sleep(0.3)
                return

            # ถ้ายังไม่เห็น Buy ให้กด Select Cookie Relay เพื่อเปิด
            res_sel = self._detect(screenshot, view_w, view_h, 'Select Cookie Relay', threshold=0.60)
            if res_sel and res_sel.get('found'):
                self.bot.log_message.emit('ok', 'Prep: tapping Select Cookie Relay')
                self._tap('Select Cookie Relay')
                self._relay_step = 1
                time.sleep(0.3)
                return

        # ──────────────────────────────────────────────────────
        # 2. Random Boost & Target Buff flow (ถ้าเปิดใช้งาน)
        # ──────────────────────────────────────────────────────
        if random_boost_enabled and self._boost_step < 3:
            # ตรวจสอบว่าได้ Target Buff แล้วหรือยัง (SelectFo)
            res_fo = self._detect(screenshot, view_w, view_h, 'SelectFo')
            if res_fo and res_fo.get('found') and res_fo.get('text'):
                text = res_fo['text']
                if self._is_target_buff_matched(text, target):
                    self.bot.log_message.emit('ok', 'Prep: target buff found: "%s"!' % text)
                    self._tap('SelectFo')
                    self._boost_step = 3
                    self._multi_buy_clicked = False
                    time.sleep(0.4)
                    return

            # ตรวจสอบปุ่ม Multi Buy
            res_mb = self._detect(screenshot, view_w, view_h, 'Multi Buy', threshold=0.55)
            if res_mb and res_mb.get('found'):
                now = time.time()
                # ถ้ายังไม่ได้กด หรือเคยกดไปแล้วเกิน 1.2 วินาที (กดพลาด / สุ่มจบแล้วยังไม่ใช่เป้าหมาย) ให้กดสุ่มต่อ
                if not self._multi_buy_clicked or (now - self._last_roll_time >= 1.2):
                    self.bot.log_message.emit('ok', 'Prep: rolling Multi Buy...')
                    self._tap('Multi Buy')
                    self._multi_buy_clicked = True
                    self._last_roll_time = now
                    self._boost_step = 2
                    time.sleep(0.3)
                return

            # ถ้ายังไม่เห็น Multi Buy ให้ตรวจหา Multi Tab
            res_tab = self._detect(screenshot, view_w, view_h, 'Multi Tab', threshold=0.60)
            if res_tab and res_tab.get('found'):
                self.bot.log_message.emit('ok', 'Prep: tapping Multi Tab')
                self._tap('Multi Tab')
                self._boost_step = 2
                self._multi_buy_clicked = False
                time.sleep(0.4)
                return

            # ถ้ายังไม่เห็นทั้ง Multi Buy และ Multi Tab ให้ตรวจหา Random Boost เพื่อเปิดหน้าต่างสุ่ม
            res_rb = self._detect(screenshot, view_w, view_h, 'Random Boost', threshold=0.60)
            if res_rb and res_rb.get('found'):
                self.bot.log_message.emit('ok', 'Prep: tapping Random Boost')
                self._tap('Random Boost')
                self._boost_step = 1
                self._multi_buy_clicked = False
                time.sleep(0.4)
                return

        # ──────────────────────────────────────────────────────
        # 3. Start Game → กดเมื่อพร้อมเล่น (Boost และ Relay เสร็จแล้ว หรือถูกปิด)
        # ──────────────────────────────────────────────────────
        is_relay_ready = (not cookie_relay_enabled) or (self._relay_step >= 2)
        is_boost_ready = (not random_boost_enabled) or (self._boost_step >= 3)

        if is_relay_ready and is_boost_ready:
            result = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.50)
            if result and result.get('found'):
                self.bot.log_message.emit('ok', 'Prep: pressing Start Game')
                self._tap('Start Game')
                time.sleep(0.5)
                self.bot.state = BotState('gameplay')
                self.bot._force_until = time.time() + 2
                return

            
    def _detect(self, screenshot, view_w, view_h, point_name, stage='prep', threshold=0.75):
        cfg = self.app.config
        coords = cfg.get_coords(stage)
        for p in coords:
            if p[0] == point_name:
                det_type = cfg.get_detection(point_name)
                result = self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, point_name, det_type, stage, threshold=threshold)
                return result
        return None

    def _tap(self, point_name, stage='prep'):
        cfg = self.app.config
        coords = cfg.get_coords(stage)
        for p in coords:
            if p[0] == point_name:
                self.app.emulator.tap(p[1], p[2])
                lc = self.app.emulator.last_click
                #if lc:
                    #self.bot.log_message.emit('info', 'Prep: tapped %s @ x=%.1f y=%.1f'% (point_name, lc[0], lc[1]))
                time.sleep(0.3)
                return True
        return False

    def _check_prep(self, screenshot, view_w, view_h):
        """Check if on prep screen."""
        for name in ['Template Prep', 'Start Game', 'Random Boost', 'Multi Tab', 'Multi Buy',
                     'Select Cookie Relay', 'Buy Cookie Relay']:
            result = self._detect(screenshot, view_w, view_h, name, threshold=0.65)
            if result and result.get('found'):
                return True
        return False

    def _is_target_buff_matched(self, text, target):
        if not text or not target:
            return False

        def clean(s):
            return ''.join(c for c in s.lower() if c.isalnum())

        clean_text = clean(text)
        clean_target = clean(target)

        # 1. Direct or normalized match
        if clean_target and (clean_target in clean_text or clean_text in clean_target):
            return True

        # 2. Keyword-based matching for known buffs
        buff_keywords = {
            'Double Coins': ['double', 'coin'],
            '15% Score Bonus': ['15', 'score'],
            '-15% HP drain': ['15', 'drain'],
            'Revive once with 80 HP': ['revive', '80'],
            '70% Crush Chance': ['70', 'crush'],
            '+17% base speed': ['17', 'base', 'speed'],
            'Gold Coin Magic': ['magic', 'gold'],
            '30% Collision Damage': ['30', 'collision'],
            '20% HP From Potions': ['20', 'potion'],
            'Magnetic Aura': ['magnet', 'aura'],
            '2 Pit Lifts': ['pit', 'lift'],
        }

        keywords = buff_keywords.get(target)
        if keywords:
            t_lower = text.lower()
            if all(k in t_lower for k in keywords):
                return True
        else:
            tokens = [t.lower() for t in target.split() if len(t) > 2]
            if tokens and sum(1 for t in tokens if t in text.lower()) >= max(1, int(len(tokens) * 0.7)):
                return True

        return False

