"""Sidebar — เมนูนำทางด้านซ้าย (Dashboard / Settings / Coordinates) (PyQt6)."""
import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from ui import theme

NAV_ITEMS = [
    ('dashboard', theme.ICON['dashboard'], 'Dashboard'),
    ('settings', theme.ICON['settings'], 'Settings'),
    ('coordinates', theme.ICON['coordinates'], 'Coordinates'),
]


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class Sidebar(QFrame):

    def __init__(self, parent=None, on_navigate=None):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.setFixedWidth(184)
        self.setStyleSheet('Sidebar { background: %s; }' % theme.BG_SIDEBAR)
        self._on_navigate = on_navigate
        self._active = 'dashboard'
        self._buttons = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 10)
        root.setSpacing(0)
        self._build_logo(root)
        self._build_nav(root)
        root.addStretch(1)
        self._build_footer(root)

    def _build_logo(self, root):
        box = QFrame(self)
        box.setObjectName('transparent')
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        badge = QLabel(theme.ICON['logo'], box)
        badge.setFont(theme.qfont(theme.FONT_FAMILY, 20, True))
        badge.setStyleSheet('color: %s;' % theme.YELLOW)
        badge.setFixedWidth(40)
        h.addWidget(badge)

        txt = QFrame(box)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        name = QLabel('CookieRun', txt)
        name.setFont(theme.qfont(theme.FONT_FAMILY, 12, True))
        name.setStyleSheet('color: %s;' % theme.YELLOW)
        v.addWidget(name)
        sub = QLabel('CLASSIC BOT', txt)
        sub.setFont(theme.qfont(*theme.XS_FONT))
        sub.setStyleSheet('color: %s;' % theme.FG_MUTED)
        v.addWidget(sub)
        h.addWidget(txt)
        root.addWidget(box)

        sep = QFrame(self)
        sep.setProperty('sep', True)
        sep.setFixedHeight(1)
        root.addSpacing(10)
        root.addWidget(sep)
        root.addSpacing(6)

    def _build_nav(self, root):
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key, icon, label in NAV_ITEMS:
            btn = QPushButton('%s   %s' % (icon, label), self)
            btn.setProperty('btn', 'nav')
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(theme.qfont(*theme.NAV_FONT))
            btn.clicked.connect(lambda _=False, k=key: self._navigate(k))
            self._group.addButton(btn)
            root.addWidget(btn)
            root.addSpacing(2)
            self._buttons[key] = btn
        self._style()

    def _build_footer(self, root):
        footer = QFrame(self)
        footer.setObjectName('card')
        v = QVBoxLayout(footer)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)

        lbl = QLabel('SYSTEM', footer)
        lbl.setFont(theme.qfont(*theme.XS_FONT))
        lbl.setProperty('role', 'muted')
        v.addWidget(lbl)

        self.clock_lbl = QLabel('--:--:--', footer)
        self.clock_lbl.setFont(theme.qfont(*theme.MONO_FONT))
        self.clock_lbl.setStyleSheet('color: %s;' % theme.FG_DIM)
        v.addWidget(self.clock_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        root.addWidget(footer)

    def _tick(self):
        self.clock_lbl.setText(time.strftime('%H:%M:%S'))

    # ── Behaviour ────────────────────────────────────────
    def _navigate(self, key):
        if key == self._active:
            return
        self._active = key
        self._style()
        if self._on_navigate:
            self._on_navigate(key)

    def _style(self):
        for key, btn in self._buttons.items():
            active = (key == self._active)
            btn.setChecked(active)
            btn.setProperty('active', active)
            btn.setFont(theme.qfont(
                *theme.NAV_FONT_ACTIVE if active else theme.NAV_FONT))
            _repolish(btn)

    def set_active(self, key):
        self._active = key
        self._style()
