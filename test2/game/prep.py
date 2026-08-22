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
        self._relay_step = 0
        self._boost_step = 0
        self._retry_count = 0
        self._roll_time = 0

    def reset(self):
        self._relay_step = 0
        self._boost_step = 0
        self._retry_count = 0
        self._roll_time = 0

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
                #self.bot.log_message.emit('ok', 'Prep: tapping Buy Cookie Relay')
                self._tap_retry('Buy Cookie Relay')
                self._relay_step = 2
                time.sleep(0.3)
                return

            # ถ้ายังไม่เห็น Buy ให้กด Select Cookie Relay เพื่อเปิด
            res_sel = self._detect(screenshot, view_w, view_h, 'Select Cookie Relay', threshold=0.60)
            if res_sel and res_sel.get('found'):
                #self.bot.log_message.emit('ok', 'Prep: tapping Select Cookie Relay')
                self._tap_retry('Select Cookie Relay')
                self._relay_step = 1
                time.sleep(0.3)
                return

        # ──────────────────────────────────────────────────────
        # 2. Random Boost & Target Buff flow
        # ──────────────────────────────────────────────────────
        if random_boost_enabled and self._boost_step < 4:
            # ตรวจ SelectFo ก่อน → เจอ target → กด SelectFo → เสร็จ
            res_fo = self._detect(screenshot, view_w, view_h, 'SelectFo')
            if res_fo and res_fo.get('found') and res_fo.get('text'):
                text = res_fo['text']
                if self._is_target_buff_matched(text, target):
                    #self.bot.log_message.emit('ok', 'Prep: target buff found: "%s"!' % text)
                    self._tap_retry('SelectFo')
                    self._boost_step = 4
                    time.sleep(0.4)
                    return

            now = time.time()

            # ไม่เจอ → Random Boost → Multi Tab → Multi Buy → รอ → ตรวจ SelectFo → เสร็จ
            if self._boost_step == 0:
                self._tap_retry('Random Boost')
                self._boost_step = 1
                self._roll_time = now
                return

            if self._boost_step == 1 and now - self._roll_time >= 0.5:
                self._tap_retry('Multi Tab')
                self._boost_step = 2
                return

            if self._boost_step == 2 and now - self._roll_time >= 1.0:
                self._tap_retry('Multi Buy')
                self._boost_step = 3
                return

            if self._boost_step == 3 and now - self._roll_time >= 3.0:
                res_fo2 = self._detect(screenshot, view_w, view_h, 'SelectFo')
                if res_fo2 and res_fo2.get('found') and res_fo2.get('text'):
                    text2 = res_fo2['text']
                    if self._is_target_buff_matched(text2, target):
                        #self.bot.log_message.emit('ok', 'Prep: target buff found: "%s"!' % text2)
                        self._tap_retry('SelectFo')
                        self._boost_step = 4
                        time.sleep(0.4)
                        return

            return

        # ──────────────────────────────────────────────────────
        # 3. Start Game → กดเมื่อพร้อมเล่น (Boost และ Relay เสร็จแล้ว หรือถูกปิด)
        # ──────────────────────────────────────────────────────
        # Ensure start button is pressed reliably
        is_relay_ready = (not cookie_relay_enabled) or (self._relay_step >= 2)
        is_boost_ready = (not random_boost_enabled) or (self._boost_step >= 4)

        if is_relay_ready and is_boost_ready:
            # Try detecting the Start Game button up to 8 attempts with a low threshold
            for attempt in range(8):
                result = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.30)
                if result and result.get('found'):
                    #self.bot.log_message.emit('ok', f'Prep: pressing Start Game (attempt {attempt + 1})')
                    self._tap('Start Game')
                    # Verify that the bot has moved to gameplay; if not, retry tap up to 2 extra times
                    for verify in range(2):
                        time.sleep(0.4)
                        if self.bot.state.value == 'gameplay':
                            break
                        #self.bot.log_message.emit('warn', f'Prep: Start Game tap did not change stage, retry {verify + 1}')
                        self._tap('Start Game')
                    self.bot.state = BotState('gameplay')
                    self.bot._force_until = time.time() + 2
                    return
                # Not found, wait a bit before next attempt
                time.sleep(0.3)
            # After all attempts, log warning and perform a final forced tap
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
                time.sleep(0.3)
                return True
        return False

    def _tap_retry(self, point_name, stage='prep', retries=2, delay=0.4):
        for i in range(retries + 1):
            if self._tap(point_name, stage):
                return True
            if i < retries:
                time.sleep(delay)
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

