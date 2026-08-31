"""Settings — หน้าตั้งค่า: Emulator, พฤติกรรมบอท, ซื้ออัตโนมัติ, buff เป้าหมาย (PyQt6)."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ui import theme
from ui.components import ConfirmDialog, MechPanel, MechButton
from ui.dropdown import Dropdown
from core.responsive import make_grid


class ToggleSwitch(QWidget):
    """Custom toggle switch matching original CTkSwitch style."""

    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(40, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked
        self.update()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._checked:
            p.setBrush(QColor(theme.ACCENT))
            p.setPen(QPen(QColor(theme.ACCENT_GLOW), 1))
        else:
            p.setBrush(QColor(theme.BG_INPUT))
            p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRoundedRect(QRectF(0, 0, 40, 24), 12, 12)
        if self._checked:
            p.setBrush(QColor('#0B0E14'))
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(theme.FG_DIM))
            p.setPen(Qt.PenStyle.NoPen)
        x = 22 if self._checked else 4
        p.drawEllipse(QRectF(x, 4, 16, 16))
        p.end()

EMULATORS = ['Auto Detect', 'LDPlayer', 'MuMu Player', 'NoxPlayer', 'BlueStacks', 'MEmu Play']

FARM_MODES = [
    ('farm_gold', 'Farm Gold'),
    ('farm_exp', 'Farm EXP'),
    ('farm_box', 'Farm Box (no jump)'),
    ('open_gitbox', 'Open Gitbox'),
]

BUFFS = [
    'Double Coins', '15% Score Bonus', '-15% HP drain',
    'Revive once with 80 HP', '70% Crush Chance', '+17% base speed',
    'Gold Coin Magic', '30% Collision Damage', '20% HP From Potions',
    'Magnetic Aura', '2 Pit Lifts',
]


class SettingRow(QFrame):
    """แถวตั้งค่า — ป้ายชื่อซ้าย + ตัวควบคุมขวา (ยืดตามกริด)."""

    def __init__(self, parent, title, hint=None, control=None):
        super().__init__(parent)
        self.setObjectName('transparent')
        self._control = control
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(8)

        txt = QFrame(self)
        txt.setObjectName('transparent')
        txt.setMinimumWidth(100)
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        title_lbl = QLabel(title, txt)
        title_lbl.setFont(theme.qfont(*theme.BODY_FONT))
        v.addWidget(title_lbl)
        if hint:
            hint_lbl = QLabel(hint, txt)
            hint_lbl.setFont(theme.qfont(*theme.XS_FONT))
            hint_lbl.setProperty('role', 'muted')
            hint_lbl.setWordWrap(True)
            v.addWidget(hint_lbl)
        root.addWidget(txt, 1)
        if control is not None:
            root.addWidget(control)


class Settings(QFrame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._loading = False
        self._build()
        self._load_config()
        for key, edit in self._num_fields.items():
            edit.textChanged.connect(lambda _, k=key: self._on_save())

    def _build(self):
        make_grid(self, columns=2, rows=2, col_weights=[5, 5],
                  row_weights=[1, 0])
        self._build_engine()
        self._build_auto()
        self._build_actions()

    def _section(self, title, icon):
        card = MechPanel(self, chamfer=10, style='diagonal', bg_color='#111722')
        card.setMinimumWidth(300)
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(6)
        head = QLabel('%s  %s' % (icon, title), card)
        head.setProperty('role', 'section')
        head.setFont(theme.qfont(*theme.SECTION_FONT))
        v.addWidget(head)
        return card, v

    # ── ซ้าย: Emulator + พฤติกรรมบอท ─────────────────────
    def _build_engine(self):
        card, v = self._section('BOT ENGINE', '\u2699')
        self.layout().addWidget(card, 0, 0)

        self.emu_menu = Dropdown(card, items=EMULATORS,
                                 placeholder='Select Emulator',
                                 max_visible=5)
        self.emu_menu.setFixedWidth(160)
        self.emu_menu.current_changed.connect(lambda _: self._on_save())
        v.addWidget(SettingRow(card, 'EMULATOR',
                               'Auto detect running LDPlayer, Nox, MuMu, BlueStacks',
                               self.emu_menu))

        self.farm_menu = Dropdown(card, items=FARM_MODES,
                                  placeholder='Farm Mode')
        self.farm_menu.setFixedWidth(160)
        self.farm_menu.current_changed.connect(lambda _: self._on_save())
        v.addWidget(SettingRow(card, 'FARM MODE',
                               'Gold / EXP / Mystery Box',
                               self.farm_menu))

        self._num_fields = {}
        self._loading = True
        for key, title, hint, default in (
            ('jump_interval', 'JUMP INTERVAL (s)', 'Time between jump taps', '0.40'),
            ('click_delay_min', 'TAP DELAY MIN (s)', 'Min randomize tap delay', '0.05'),
            ('click_delay_max', 'TAP DELAY MAX (s)', 'Max randomize tap delay', '0.15'),
            ('click_hold', 'TAP HOLD (s)', 'Duration button is held', '0.05'),
            ('click_jitter_pct', 'TAP JITTER (%)', 'Random position offset (percent)', '2.0'),
            ('click_jitter_px', 'TAP JITTER (px)', 'Pixel offset fallback', '3.0'),
            ('fast_start_delay', 'FAST START DELAY (s)', 'Pause before starting run', '1.0'),
        ):
            edit = QLineEdit(card)
            edit.setText(default)
            edit.setFixedWidth(80)
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._num_fields[key] = edit
            v.addWidget(SettingRow(card, title, hint, edit))

        v.addStretch(1)

    # ── ขวา: ซื้ออัตโนมัติ / ตรวจสอบ ─────────────────────
    def _build_auto(self):
        card, v = self._section('AUTOMATION & BOOSTS', '\u26A1')
        self.layout().addWidget(card, 0, 1)

        self._switches = {}
        for key, title, hint_text, default in (
            ('fast_start', 'FAST START', 'Tap through intro screen immediately', True),
            ('cookie_relay', 'RELAY COOKIE', 'Auto tap relay cookie when main falls', True),
            ('relic_check', 'RELIC CHECKS', 'Check for mystery box relic popup', True),
            ('random_boost', 'BUY BOOST', 'Auto buy random boost before run', True),
        ):
            sw = ToggleSwitch(card, checked=default)
            sw.mousePressEvent = (
                lambda event, s=sw, k=key: self._handle_switch(s, k, event))
            self._switches[key] = sw
            v.addWidget(SettingRow(card, title, hint_text, sw))

        self.buff_menu = Dropdown(card, items=BUFFS,
                                  placeholder='Target Buff',
                                  max_visible=6)
        self.buff_menu.setFixedWidth(160)
        self.buff_menu.current_changed.connect(lambda _: self._on_save())
        v.addWidget(SettingRow(card, 'TARGET BUFF',
                               'Reroll random boost until matching this',
                               self.buff_menu))

        v.addStretch(1)

    def _handle_switch(self, sw, key, event):
        ToggleSwitch.mousePressEvent(sw, event)
        self._on_save()

    # ── แถบล่าง: Reset / Save ────────────────────────────
    def _build_actions(self):
        bar = MechPanel(self, chamfer=8, style='diagonal', bg_color='#111722')
        self.layout().addWidget(bar, 1, 0, 1, 2)
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 8, 14, 8)

        self.save_lbl = QLabel('', bar)
        self.save_lbl.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        self.save_lbl.setStyleSheet('color: %s;' % theme.GREEN)
        h.addWidget(self.save_lbl)
        h.addStretch(1)

        btn_reset = MechButton('RESET DEFAULTS', bar, chamfer=8, btn_type='dark')
        btn_reset.setFont(theme.qfont(theme.FONT_FAMILY, 8, True))
        btn_reset.setFixedHeight(32)
        btn_reset.clicked.connect(self._on_reset)
        h.addWidget(btn_reset)

        btn_save = MechButton('SAVE SETTINGS', bar, chamfer=8, btn_type='engage')
        btn_save.setFont(theme.qfont(theme.FONT_FAMILY, 9, True))
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._on_save)
        h.addWidget(btn_save)

    # ── Actions ──────────────────────────────────────────
    def _load_config(self):
        self._loading = True
        try:
            cfg = getattr(self.app, 'config', None)
            if cfg is None:
                return
            settings = cfg.settings
            self.emu_menu.set_current(settings.get('emulator', 'LDPlayer'))
            farm_mode = settings.get('farm_mode', 'farm_gold')
            self.farm_menu.set_current(farm_mode)
            for key in ('jump_interval', 'click_delay_min',
                        'click_delay_max', 'click_hold',
                        'click_jitter_pct', 'click_jitter_px',
                        'fast_start_delay'):
                if key in settings and key in self._num_fields:
                    self._num_fields[key].setText(str(settings[key]))
            for key in self._switches:
                if key in settings:
                    self._switches[key].setChecked(bool(settings[key]))
            target = settings.get('target_buff', '')
            if target:
                self.buff_menu.set_current(target)
        finally:
            self._loading = False


    def _on_save(self, notify=True):
        if self._loading:
            return

        data = {
            'emulator': self.emu_menu.current_text(),
            'farm_mode': self.farm_menu.current_key(),
            'jump_interval': self._num_fields['jump_interval'].text(),
            'click_delay_min': self._num_fields['click_delay_min'].text(),
            'click_delay_max': self._num_fields['click_delay_max'].text(),
            'click_hold': self._num_fields['click_hold'].text(),
            'click_jitter_pct': self._num_fields['click_jitter_pct'].text(),
            'click_jitter_px': self._num_fields['click_jitter_px'].text(),
            'fast_start_delay': self._num_fields['fast_start_delay'].text(),
            'fast_start': self._switches['fast_start'].isChecked(),
            'cookie_relay': self._switches['cookie_relay'].isChecked(),
            'relic_check': self._switches['relic_check'].isChecked(),
            'random_boost': self._switches['random_boost'].isChecked(),
            'target_buff': self.buff_menu.current_text(),
        }
        if notify:
            self.save_lbl.setText('\u2713  Settings saved')
        if hasattr(self.app, 'save_settings'):
            self.app.save_settings(data, notify=notify)

    def _on_reset(self):
        dlg = ConfirmDialog(
            self, 'Reset Settings',
            'Reset all settings to default values?',
            confirm_text='Reset', level='warn')
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.emu_menu.set_current('LDPlayer')
        self.farm_menu.set_current('farm_gold')
        self._num_fields['jump_interval'].setText('0.80')
        self._num_fields['click_delay_min'].setText('0.05')
        self._num_fields['click_delay_max'].setText('0.15')
        self._num_fields['click_hold'].setText('0.05')
        self._num_fields['click_jitter_pct'].setText('2.0')
        self._num_fields['click_jitter_px'].setText('3.0')
        self._num_fields['fast_start_delay'].setText('1.0')
        self._switches['fast_start'].setChecked(True)
        self._switches['cookie_relay'].setChecked(True)
        self._switches['relic_check'].setChecked(True)
        self._switches['random_boost'].setChecked(True)
        self.buff_menu.set_current('Double Coins')
        self.save_lbl.setText('')
        if hasattr(self.app, 'show_toast'):
            self.app.show_toast('ok', 'Settings reset to defaults')
