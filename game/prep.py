"""game/prep.py -- Prep stage handler."""
import time
import logging

from vision.engine import VisionEngine
from game.state import BotState

log = logging.getLogger(__name__)

# ถ้ารอ target buff นานเกินนี้ (วินาที) ให้ข้ามและกด Start Game เลย
_BOOST_TIMEOUT = 12.0

# ถ้า tap Select วนหา Fast Start / Cookie Relay ยังไม่เจอคำที่ต้องการให้ครบเวลานี้ -> ข้าม
_SELECT_TIMEOUT = 10.0


class PrepHandler:
    """Handles prep screen: cookie relay, boost, target buff, start game."""

    def __init__(self, bot):
        self.bot = bot
        self.app = bot.app
        self.engine = VisionEngine()
        self._fast_step = 0
        self._relay_step = 0
        self._boost_step = 0
        self._retry_count = 0
        self._roll_time = 0
        self._fast_select_time = 0
        self._relay_select_time = 0

    def reset(self):
        self._fast_step = 0
        self._relay_step = 0
        self._boost_step = 0
        self._retry_count = 0
        self._roll_time = 0
        self._fast_select_time = 0
        self._relay_select_time = 0

    def run(self, screenshot, view_w, view_h):
        fast_start_enabled = self.app.config.settings.get('fast_start', True)        
        cookie_relay_enabled = self.app.config.settings.get('cookie_relay', True)
        rb_enabled = self.app.config.settings.get('random_boost', True)

        # ── ถ้าปิดทั้ง 3 ตัว → กด Start Game เลย ──
        if not fast_start_enabled and not cookie_relay_enabled and not rb_enabled:
            if self._fast_step == 0 and self._relay_step == 0 and self._boost_step == 0:
                res = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.60)
                if res and res.get('found'):
                    self._tap_retry('Start Game')
                    self._boost_step = 5
                    time.sleep(0.3)
                    self.bot.log_message.emit('ok', 'Fast Start/Relay/Boost ปิดหมด → Start Game เลย')
                    return

        # ──────────────────────────────────────────────────────
        # 1. Fast Start flow (อันดับ 1)
        # ──────────────────────────────────────────────────────
        if fast_start_enabled and self._fast_step < 2:
            if self._fast_step == 0:
                if self._tap('Select Fast Start'):
                    time.sleep(0.3)
                    res_rel = self._detect(
                        screenshot, view_w, view_h,
                        'Buy Fast Start', threshold=0.60
                    )
                    if res_rel and res_rel.get('found'):
                        self._fast_step = 1
                        return
                    else:
                        self.bot.log_message.emit('warn', 'Fast Start: step0 — Buy ไม่เจอ → tap พลาด อยู่ step0 ต่อ')
                else:
                    self.bot.log_message.emit('err', 'Fast Start: step0 — ไม่มีพิกัด Select Fast Start')
                return


            if self._fast_step == 1:
                res_buy = self._detect(screenshot, view_w, view_h, 'Buy Fast Start', threshold=0.60)
                if res_buy and res_buy.get('found'):
                    self._tap_retry('Buy Fast Start')
                    self._fast_step = 2
                    time.sleep(0.3)
                    self.bot.log_message.emit('ok', 'Fast Start: สำเร็จ')
                    return


        # ──────────────────────────────────────────────────────
        # 2. Cookie Relay flow (อันดับ 2)
        # ──────────────────────────────────────────────────────
        if cookie_relay_enabled and self._relay_step < 2:
            if self._relay_step == 0:
                if self._tap('Select Cookie Relay'):
                    time.sleep(0.3)
                    res_buy = self._detect(
                        screenshot, view_w, view_h,
                        'Buy Cookie Relay', threshold=0.60
                    )
                    if res_buy and res_buy.get('found'):
                        self._relay_step = 1
                        return
                    else:
                        self.bot.log_message.emit('warn', 'Cookie Relay: step0 — Buy ไม่เจอ → tap พลาด อยู่ step0 ต่อ')
                else:
                    self.bot.log_message.emit('err', 'Cookie Relay: step0 — ไม่มีพิกัด Select Cookie Relay')
                return


            if self._relay_step == 1:
                res_buy = self._detect(screenshot, view_w, view_h, 'Buy Cookie Relay', threshold=0.60)
                if res_buy and res_buy.get('found'):
                    self._tap_retry('Buy Cookie Relay')
                    self._relay_step = 2
                    time.sleep(0.3)
                    self.bot.log_message.emit('ok', 'Cookie Relay: สำเร็จ')
                    return


        if rb_enabled and self._boost_step < 5:
            # ── เช็ค SelectFo ก่อน ถ้า target buff ตรง ข้าม boost ไปกด Start Game เลย ──
            if self._boost_step == 0:
                target_buff = self.app.config.settings.get('target_buff', '')
                if target_buff:
                    res_fo = self._detect(screenshot, view_w, view_h, 'SelectFo', threshold=0.60)
                    if res_fo and res_fo.get('found'):
                        fo_text = res_fo.get('text', '') or ''
                        if self._is_target_buff_matched(fo_text, target_buff):
                            res_start = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.60)
                            if res_start and res_start.get('found'):
                                self._tap_retry('Start Game')
                                self._boost_step = 5
                                time.sleep(0.3)
                                self.bot.log_message.emit('ok', 'Target buff ตรง — ข้าม Random Boost → Start Game')
                                return

            if self._boost_step == 0:
                if self._tap('Random Boost'):
                    time.sleep(0.3)
                    res = self._detect(screenshot, view_w, view_h, 'Multi Tab', threshold=0.60)
                    if res and res.get('found'):
                        self._boost_step = 1
                        return
                else:
                    self.bot.log_message.emit('err', 'Random Boost: ไม่มีพิกัด Random Boost')
                return


            if self._boost_step == 1:
                res = self._detect(screenshot, view_w, view_h, 'Multi Tab', threshold=0.60)
                if res and res.get('found'):
                    self._tap_retry('Multi Tab')
                    time.sleep(0.3)
                    res2 = self._detect(screenshot, view_w, view_h, 'Multi Buy', threshold=0.60)
                    if res2 and res2.get('found'):
                        self._boost_step = 2
                        return
                return


            if self._boost_step == 2:
                res = self._detect(screenshot, view_w, view_h, 'Multi Buy', threshold=0.60)
                if res and res.get('found'):
                    self._tap_retry('Multi Buy')
                    time.sleep(0.3)
                    res2 = self._detect(screenshot, view_w, view_h, 'SelectFo', threshold=0.60)
                    if res2 and res2.get('found'):
                        self._boost_step = 3
                        return
                return


            if self._boost_step == 3:
                res = self._detect(screenshot, view_w, view_h, 'SelectFo', threshold=0.60)
                if res and res.get('found'):
                    self._tap_retry('SelectFo')
                    time.sleep(0.3)
                    res2 = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.60)
                    if res2 and res2.get('found'):
                        self._boost_step = 4
                        return
                return


            if self._boost_step == 4:
                res = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.60)
                if res and res.get('found'):
                    self._tap_retry('Start Game')
                    self._boost_step = 5
                    time.sleep(0.3)
                    self.bot.log_message.emit('ok', 'Random Boost: สำเร็จ')
                    return


    # ── Detect helper ─────────────────────────────────────
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

    def _has_coord(self, point_name, stage='prep'):
        cfg = self.app.config
        for p in cfg.get_coords(stage):
            if p[0] == point_name:
                return True
        return False

    def _select_and_buy(self, screenshot, view_w, view_h, word,
                        select_point, check_point, buy_point, start_time):
        """Tap Select ซ้ำ ๆ จนกว่า Check region จะเจอคำที่ต้องการ แล้วกด Buy.

        วนจนกว่าจะเจอ (ไปๆเรื่อย ๆ) แต่มี timeout ป้องกันค้างไม่จบ
        """
        # 1) ลอง Check ก่อน (เผื่อว่าตอนนี้แสดงตัวเลือกที่ต้องการอยู่แล้ว)
        text = self._read_check_ocr(screenshot, view_w, view_h, check_point)
        if text and word and self._word_in_text(word, text):
            log.info('Prep: เจอ %s ใน check region -> กด Buy', word)
            self._tap_retry(buy_point)
            return True

        # 2) ยังไม่เจอ -> tap Select ไปตัวเลือกถัดไป (ไปๆเรื่อย ๆ)
        if not self._has_coord(select_point):
            log.warning('Prep: no %s coord — skip', select_point)
            return True
        self._tap(select_point)

        # 3) timeout ข้าม เพื่อไม่ให้ค้างวนอยู่ตรงนี้ตลอดไป
        if start_time and time.time() - start_time >= _SELECT_TIMEOUT:
            log.warning('Prep: %s select timeout — ข้าม และกด Buy', select_point)
            self._tap_retry(buy_point)
            return True

        return False

    def _read_check_ocr(self, screenshot, view_w, view_h, check_point):
        """OCR อ่าน text ที่ check region (คืน text string หรือ '')"""
        if not self._has_coord(check_point):
            return ''
        cfg = self.app.config
        coords = cfg.get_coords('prep')
        for p in coords:
            if p[0] == check_point:
                res = self.engine.detect(
                    screenshot, p[1], p[2], p[3], p[4],
                    view_w, view_h, check_point, 'ocr', 'prep')
                if res and res.get('text'):
                    return res['text']
                return ''
        return ''

    @staticmethod
    def _word_in_text(word, text):
        def clean(s):
            return ''.join(c for c in s.lower() if c.isalnum())

        clean_word = clean(word)
        clean_text = clean(text)
        if not clean_word or not clean_text:
            return False
        return clean_word in clean_text

    def _check_prep(self, screenshot, view_w, view_h):
        """Check if on prep screen."""
        for name in ['Template Prep', 'Start Game', 'Random Boost', 'Multi Tab', 'Multi Buy',
                     'Select Cookie Relay', 'Buy Cookie Relay',
                     'Select Fast Start', 'Buy Fast Start']:
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

        if clean_target and (clean_target in clean_text or clean_text in clean_target):
            return True

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
