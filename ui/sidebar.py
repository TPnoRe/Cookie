"""Sidebar — เมนูนำทางด้านซ้าย สไตล์ Robotic Mech HUD พร้อมปุ่มและกรอบตัดมุมเฉียง (PyQt6)."""
import os
import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QLinearGradient, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from ui import theme
from ui.components import MechPanel

_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logo.png')

NAV_ITEMS = [
    ('dashboard', theme.ICON['dashboard'], 'Dashboard', '01'),
    ('settings', theme.ICON['settings'], 'Settings', '02'),
    ('coordinates', theme.ICON['coordinates'], 'Coordinates', '03'),
]


class MechNavButton(QPushButton):
    """ปุ่มนำทางตัดมุมเฉียงสไตล์หุ่นยนต์ Mecha (Chamfered Nav Button)."""

    def __init__(self, key, icon, label, code, parent=None):
        super().__init__('', parent)
        self.key = key
        self.icon_str = icon
        self.label_str = label
        self.code_str = code
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.chamfer = 8

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width() - 1
        h = self.height() - 1
        c = self.chamfer

        path = QPainterPath()
        # Cut Top-Left & Bottom-Right
        path.moveTo(c, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(0, h)
        path.lineTo(0, c)
        path.closeSubpath()

        is_active = self.isChecked()
        is_hover = self.underMouse() and not is_active

        if is_active:
            bg_grad = QLinearGradient(0, 0, w, 0)
            bg_grad.setColorAt(0.0, QColor('#0F2C3D'))
            bg_grad.setColorAt(1.0, QColor('#142334'))
            border_col = QColor(theme.ACCENT)
            text_col = QColor(theme.ACCENT)
        elif is_hover:
            bg_grad = QLinearGradient(0, 0, w, 0)
            bg_grad.setColorAt(0.0, QColor('#182232'))
            bg_grad.setColorAt(1.0, QColor('#121824'))
            border_col = QColor(theme.ACCENT_DEEP)
            text_col = QColor('#FFFFFF')
        else:
            bg_grad = QLinearGradient(0, 0, w, 0)
            bg_grad.setColorAt(0.0, QColor('#101622'))
            bg_grad.setColorAt(1.0, QColor('#0C101A'))
            border_col = QColor(theme.BORDER)
            text_col = QColor(theme.FG_DIM)

        # Fill background
        painter.setBrush(bg_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Stroke border
        bpen = QPen(border_col, 1.5 if is_active else 1.0)
        painter.setPen(bpen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Active Left Notch / Indicator
        if is_active:
            painter.setPen(QPen(QColor(theme.ACCENT), 3.0))
            painter.drawLine(0, c, 0, h)
            # Glowing corner tick
            painter.setPen(QPen(QColor(theme.ACCENT_GLOW), 2.0))
            painter.drawLine(0, c, c, 0)
            painter.drawLine(w, h - c, w - c, h)

        # Icon Rendering (Enlarged)
        painter.setFont(theme.qfont('Segoe UI Symbol', 13, bold=True))
        painter.setPen(QColor(theme.ACCENT if is_active else theme.FG_DIM))
        painter.drawText(16, int(h / 2 + 5), self.icon_str)

        # Label Text Rendering
        painter.setFont(theme.qfont(theme.FONT_FAMILY, 10, bold=is_active))
        painter.setPen(text_col)
        painter.drawText(38, int(h / 2 + 4), self.label_str)

        # Tech code on the right e.g. [01]
        painter.setFont(theme.qfont(theme.FONT_MONO, 7, bold=True))
        painter.setPen(QColor(theme.ACCENT if is_active else theme.FG_MUTED))
        painter.drawText(w - 30, int(h / 2 + 4), self.code_str)


class Sidebar(QFrame):

    def __init__(self, parent=None, on_navigate=None):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.setFixedWidth(200)
        self.setStyleSheet('Sidebar { background: %s; border-right: 1px solid %s; }' % (theme.BG_SIDEBAR, theme.BORDER))
        self._on_navigate = on_navigate
        self._active = 'dashboard'
        self._buttons = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 12)
        root.setSpacing(0)
        self._build_logo(root)
        self._build_nav(root)
        root.addStretch(1)
        self._build_footer(root)

    def _build_logo(self, root):
        logo_panel = MechPanel(self, chamfer=10, style='diagonal', bg_color='#0F1522', border_color=theme.ACCENT, glow=True)
        h = QHBoxLayout(logo_panel)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(8)

        if os.path.isfile(_LOGO_PATH):
            badge = QLabel(logo_panel)
            pixmap = QPixmap(_LOGO_PATH).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            badge.setPixmap(pixmap)
            badge.setFixedWidth(34)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            badge = QLabel(theme.ICON['logo'], logo_panel)
            badge.setFont(theme.qfont('Segoe UI Symbol', 24, True))
            badge.setStyleSheet('color: %s;' % theme.ACCENT)
            badge.setFixedWidth(34)
        h.addWidget(badge)

        txt = QFrame(logo_panel)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        name = QLabel('COOKIE RUN', txt)
        name.setFont(theme.qfont(theme.FONT_FAMILY, 10, True))
        name.setStyleSheet('color: %s; letter-spacing: 0.5px;' % theme.FG)
        v.addWidget(name)
        sub = QLabel('MECH HUD v2.1', txt)
        sub.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        sub.setStyleSheet('color: %s;' % theme.ACCENT)
        v.addWidget(sub)
        h.addWidget(txt)
        root.addWidget(logo_panel)

        root.addSpacing(14)

    def _build_nav(self, root):
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key, icon, label, code in NAV_ITEMS:
            btn = MechNavButton(key, icon, label, code, self)
            btn.clicked.connect(lambda _=False, k=key: self._navigate(k))
            self._group.addButton(btn)
            root.addWidget(btn)
            root.addSpacing(6)
            self._buttons[key] = btn
        self._style()

    def _build_footer(self, root):
        footer = MechPanel(self, chamfer=8, style='diagonal', bg_color='#111722', border_color=theme.BORDER)
        v = QVBoxLayout(footer)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel('SYS.STATUS', footer)
        lbl.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        lbl.setStyleSheet('color: %s;' % theme.FG_MUTED)
        top_row.addWidget(lbl)

        self.status_dot = QLabel('● OFFLINE', footer)
        self.status_dot.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        self.status_dot.setStyleSheet('color: %s;' % theme.FG_MUTED)
        top_row.addStretch(1)
        top_row.addWidget(self.status_dot)
        v.addLayout(top_row)

        self.clock_lbl = QLabel('--:--:--', footer)
        self.clock_lbl.setFont(theme.qfont(theme.FONT_MONO, 9, True))
        self.clock_lbl.setStyleSheet('color: %s;' % theme.ACCENT)
        v.addWidget(self.clock_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        root.addWidget(footer)

    def set_status(self, text, color=None):
        """อัปเดตข้อความและสีของ SYS.STATUS เช่น READY, RUNNING, OFFLINE, ERROR."""
        self.status_dot.setText('● ' + text.upper())
        self.status_dot.setStyleSheet('color: %s;' % (color or theme.GREEN))

    def _tick(self):
        self.clock_lbl.setText('TIME ' + time.strftime('%H:%M:%S'))

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
            btn.setChecked(key == self._active)
            btn.update()

    def set_active(self, key):
        self._active = key
        self._style()
