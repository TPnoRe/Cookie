"""Settings — หน้าตั้งค่า: Emulator, พฤติกรรมบอท, ซื้ออัตโนมัติ, buff เป้าหมาย (PyQt6)."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ui import theme
from ui.components import ConfirmDialog
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
            p.setPen(QPen(QColor(theme.ACCENT), 1))
        else:
            p.setBrush(QColor(theme.BG_INPUT))
            p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRoundedRect(QRectF(0, 0, 40, 24), 12, 12)
        if self._checked:
            p.setBrush(QColor(theme.FG_DIM))
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(theme.FG_DIM))
            p.setPen(Qt.PenStyle.NoPen)
        x = 22 if self._checked else 4
        p.drawEllipse(QRectF(x, 4, 16, 16))
        p.end()

EMULATORS = ['LDPlayer', 'NoxPlayer', 'MuMu', 'BlueStacks', 'Custom ADB']

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
        self._build()
        self._load_config()

    def _build(self):
        make_grid(self, columns=2, rows=2, col_weights=[5, 5],
                  row_weights=[1, 0])
        self._build_engine()
        self._build_auto()
        self._build_actions()

    def _section(self, title, icon):
        card = QFrame(self)
        card.setObjectName('card')
        card.setMinimumWidth(300)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
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
        v.addWidget(SettingRow(card, 'Emulator',
                               'Emulator client to control',
                               self.emu_menu))

        self.farm_menu = Dropdown(card, items=[
            (key, label) for key, label in FARM_MODES
        ], placeholder='Select Farm Mode', max_visible=4)
        self.farm_menu.setFixedWidth(160)
        v.addWidget(SettingRow(card, 'Farm Mode',
                               'Bot behavior during gameplay',
                               self.farm_menu))

        self._num_fields = {}
        num_rows = [
            ('jump_interval', 'Jump Interval (s)', '0.80'),
            ('click_delay_min', 'Click Delay Min (s)', '0.05'),
            ('click_delay_max', 'Click Delay Max (s)', '0.15'),
            ('click_hold', 'Click Hold (s)', '0.05'),
            ('click_jitter_pct', 'Click Jitter (%)', '2.0'),
            ('click_jitter_px', 'Click Jitter (px)', '3.0'),
            ('fast_start_delay', 'Fast Start Delay (s)', '1.0'),
        ]
        for key, title, val in num_rows:
            entry = QLineEdit(card)
            entry.setText(val)
            entry.setFont(theme.qfont(*theme.MONO_FONT))
            entry.setFixedWidth(80)
            self._num_fields[key] = entry
            v.addWidget(SettingRow(card, title, control=entry))

        self._switches = {}
        sw_rows = [
            ('fast_start', 'Fast Start', True),
            ('cookie_relay', 'Cookie Relay', True),
            ('relic_check', 'Relic Check', True),
        ]
        for key, title, default in sw_rows:
            sw = ToggleSwitch(card, checked=default)
            self._switches[key] = sw
            v.addWidget(SettingRow(card, title, control=sw))
        v.addStretch(1)

    # ── ขวา: buff เป้าหมาย ────────────────
    def _build_auto(self):
        card, v = self._section('AUTO PURCHASE & BUFFS', '\u2694')
        self.layout().addWidget(card, 0, 1)

        sw = ToggleSwitch(card, checked=True)
        self._switches['random_boost'] = sw
        v.addWidget(SettingRow(card, 'Random Boost',
                               'Randomize buff before start',
                               control=sw))
        v.addSpacing(6)

        lbl = QLabel('TARGET BUFF', card)
        lbl.setFont(theme.qfont(*theme.XS_FONT))
        lbl.setProperty('role', 'muted')
        v.addWidget(lbl)

        self.buff_menu = Dropdown(card, items=BUFFS,
                                   placeholder='Select Buff',
                                   max_visible=6)
        self.buff_menu.setFixedWidth(160)
        v.addWidget(self.buff_menu, 0, Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)

    def _build_actions(self):
        bar = QFrame(self)
        bar.setObjectName('transparent')
        self.layout().addWidget(bar, 1, 0, 1, 2)
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 8, 10, 10)

        self.save_lbl = QLabel('', bar)
        self.save_lbl.setFont(theme.qfont(*theme.SMALL_FONT))
        self.save_lbl.setStyleSheet('color: %s;' % theme.GREEN)
        h.addWidget(self.save_lbl)
        h.addStretch(1)

        btn_reset = QPushButton('Reset', bar)
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setFont(theme.qfont(*theme.SMALL_FONT))
        btn_reset.clicked.connect(self._on_reset)
        h.addWidget(btn_reset)

        btn_save = QPushButton('Save Settings', bar)
        btn_save.setProperty('btn', 'primary')
        btn_save.setFont(theme.qfont(*theme.BTN_FONT))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)
        h.addWidget(btn_save)

    # ── Actions ──────────────────────────────────────────
    def _load_config(self):
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

    def _on_save(self):
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
        self.save_lbl.setText('\u2713  Settings saved')
        if hasattr(self.app, 'save_settings'):
            self.app.save_settings(data)

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
