"""game/prep.py -- Prep stage handler."""
import time
import logging

from vision.engine import VisionEngine

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

    def run(self, screenshot, view_w, view_h):
        target = self.app.config.settings.get('target_buff', 'Double Coins')

        # ──────────────────────────────────────────────────────
        # ตรวจสอบ Target Buff (SelectFo)
        # ──────────────────────────────────────────────────────
        result = self._detect(screenshot, view_w, view_h, 'SelectFo')
        if result and result.get('found') and result.get('text'):
            text = result['text']
            norm_text = text.replace(' ', '').lower()
            norm_target = target.replace(' ', '').lower()
            if norm_target in norm_text:
                self.bot.log_message.emit(
                    'ok', 'Prep: [boost_step=%d] target buff found: "%s"!'
                    % (self._boost_step, text))
                # แตะยืนยันบัฟ หรือกด Start Game
                self._tap('SelectFo')
                self._boost_step = 3
                self._multi_buy_clicked = False
                time.sleep(0.3)
                self._tap('Start Game')
                return

        # ──────────────────────────────────────────────────────
        # Cookie Relay flow แบบ step-by-step พร้อม verify ทุกขั้น
        # ──────────────────────────────────────────────────────
        cookie_relay_enabled = self.app.config.settings.get('cookie_relay', True)
        if cookie_relay_enabled and self._relay_step < 2:
            # Step 0 → ต้องเห็น Select Cookie Relay ก่อนถึงจะกด
            if self._relay_step == 0:
                result = self._detect(screenshot, view_w, view_h, 'Select Cookie Relay', threshold=0.65)
                if result and result.get('found'):
                    self.bot.log_message.emit(
                        'info', 'Prep: [relay_step=0] tapping Select Cookie Relay')
                    self._tap('Select Cookie Relay')
                    self._relay_step = 1
                    return

            # Step 1 → ต้องเห็น Buy Cookie Relay ก่อนถึงจะกด
            if self._relay_step == 1:
                result = self._detect(screenshot, view_w, view_h, 'Buy Cookie Relay', threshold=0.65)
                if result and result.get('found'):
                    self.bot.log_message.emit(
                        'info', 'Prep: [relay_step=1] tapping Buy Cookie Relay')
                    self._tap('Buy Cookie Relay')
                    self._relay_step = 2
                    return
                # ถ้าไม่เห็น Buy → อาจกด Select ไม่ติด ลองใหม่
                result2 = self._detect(screenshot, view_w, view_h, 'Select Cookie Relay', threshold=0.65)
                if result2 and result2.get('found'):
                    self.bot.log_message.emit(
                        'warn', 'Prep: [relay_step=1] retry Select Cookie Relay')
                    self._tap('Select Cookie Relay')
                    return

        # ──────────────────────────────────────────────────────
        # Boost flow แบบ step-by-step พร้อม verify ทุกขั้น
        # ──────────────────────────────────────────────────────
        if self._boost_step < 3:
            # Step 0 → ต้องเห็น Random Boost ก่อน
            if self._boost_step == 0:
                result = self._detect(screenshot, view_w, view_h, 'Random Boost', threshold=0.65)
                if result and result.get('found'):
                    self.bot.log_message.emit(
                        'info', 'Prep: [boost_step=0] tapping Random Boost (conf=%.2f)'
                        % result.get('confidence', 0.0))
                    self._tap('Random Boost')
                    self._boost_step = 1
                    self._multi_buy_clicked = False
                    self._retry_count = 0
                return  # ยังไม่เสร็จ boost → ห้ามกด Start Game

            # Step 1 → ต้องเห็น Multi Tab ก่อน
            if self._boost_step == 1:
                result = self._detect(screenshot, view_w, view_h, 'Multi Tab', threshold=0.60)
                if result and result.get('found'):
                    self.bot.log_message.emit(
                        'info', 'Prep: [boost_step=1] tapping Multi Tab (conf=%.2f)'
                        % result.get('confidence', 0.0))
                    self._tap('Multi Tab')
                    self._boost_step = 2
                    self._multi_buy_clicked = False
                    self._retry_count = 0
                    time.sleep(0.5)
                    return
                
                # ถ้าไม่เห็น Multi Tab ลองหา Random Boost ซ้ำ
                self._retry_count += 1
                if self._retry_count > 3:
                    result2 = self._detect(screenshot, view_w, view_h, 'Random Boost', threshold=0.65)
                    if result2 and result2.get('found'):
                        self.bot.log_message.emit(
                            'warn', 'Prep: [boost_step=1] retry Random Boost (retry_count=%d)'
                            % self._retry_count)
                        self._tap('Random Boost')
                        self._retry_count = 0
                return  # ยังไม่เสร็จ boost → ห้ามกด Start Game

            # Step 2 → อยู่ในหน้า Multi Tab ให้กด Multi Buy รอ จนกว่าจะได้ Target Buff
            # หากไม่เจอ Multi Buy ให้กด Random Boost > Multi Tab ใหม่อีกรอบ
            # และหากกด Multi Buy พลาดก็ให้กด Multi Buy อีกรอบ ขั้นตอนนี้คือเฉพาะตอนกดพลาด
            if self._boost_step == 2:
                result_mb = self._detect(screenshot, view_w, view_h, 'Multi Buy', threshold=0.55)
                if result_mb and result_mb.get('found'):
                    conf = result_mb.get('confidence', 0.0)
                    now = time.time()
                    if not self._multi_buy_clicked:
                        self.bot.log_message.emit(
                            'info', 'Prep: [boost_step=2] tapping Multi Buy (conf=%.2f), waiting for target buff...' % conf)
                        self._tap('Multi Buy')
                        self._multi_buy_clicked = True
                        self._last_roll_time = now
                        self._retry_count = 0
                        time.sleep(0.4)
                        return
                    elif now - self._last_roll_time >= 1.5:
                        # กดพลาด (ปุ่ม Multi Buy ยังคงอยู่หลังจากกดไปแล้ว 1.5 วิ) -> ให้กด Multi Buy ซ้ำเฉพาะตอนกดพลาด
                        self.bot.log_message.emit(
                            'warn', 'Prep: [boost_step=2] retry Multi Buy (missed previous tap, conf=%.2f)' % conf)
                        self._tap('Multi Buy')
                        self._last_roll_time = now
                        self._retry_count = 0
                        time.sleep(0.4)
                        return
                    else:
                        # กำลังรอผลการสุ่ม
                        return
                else:
                    # ไม่เห็นปุ่ม Multi Buy
                    if self._multi_buy_clicked:
                        # เคยกดไปแล้ว และกำลังหมุนสุ่มบัฟอยู่ -> ให้รอต่อไป
                        return

                    # ยังไม่เคยกด Multi Buy แต่หาปุ่มไม่พบ
                    self._retry_count += 1
                    if self._retry_count > 3:
                        # หากไม่เจอ Multi Buy ให้กด Random Boost > Multi Tab ใหม่อีกรอบ
                        self.bot.log_message.emit(
                            'warn', 'Prep: [boost_step=2] Multi Buy not found -> restarting Random Boost flow')
                        self._boost_step = 0
                        self._multi_buy_clicked = False
                        self._retry_count = 0
                    return

        # ──────────────────────────────────────────────────────
        # Start Game → กดได้เมื่อ boost เสร็จ (_boost_step == 3)
        # ──────────────────────────────────────────────────────
        result = self._detect(screenshot, view_w, view_h, 'Start Game', threshold=0.65)
        if result and result.get('found'):
            self.bot.log_message.emit(
                'info', 'Prep: [boost_step=%d] pressing Start Game' % self._boost_step)
            self._tap('Start Game')

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
                if lc:
                    self.bot.log_message.emit(
                        'info', 'Prep: tapped %s @ x=%.1f y=%.1f'
                        % (point_name, lc[0], lc[1]))
                time.sleep(0.3)
                return True
        return False

    def _check_prep(self, screenshot, view_w, view_h):
        """Check if on prep screen."""
        for name in ['Template Prep', 'Start Game', 'Random Boost', 'Multi Tab', 'Multi Buy',
                     'Select Cookie Relay', 'Buy Cookie Relay']:
            result = self._detect(screenshot, view_w, view_h, name, threshold=0.60)
            if result and result.get('found'):
                return True
        return False
