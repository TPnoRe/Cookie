"""TopBar — แถบหัวข้อหน้า สไตล์ Robotic Mech HUD พร้อมกรอบตัดมุมเฉียง (PyQt6)."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui import theme
from ui.components import MechPanel

PAGES = {
    'dashboard': ('Dashboard', 'Live HUD Telemetry & Automation', theme.ICON['dashboard']),
    'settings': ('System Config', 'Core Engine & Automation Parameters', theme.ICON['settings']),
    'coordinates': ('Coordinates Matrix', 'Calibrate Screen Coordinate Targets', theme.ICON['coordinates']),
}


class TopBar(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.setFixedHeight(50)
        self._build()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(theme.BG))

        # Bottom Border with Step Line Accent
        painter.setPen(QPen(QColor(theme.BORDER), 1.2))
        painter.drawLine(0, h - 1, w, h - 1)

        # Top Neon Accent Line
        painter.setPen(QPen(QColor(theme.ACCENT), 2.0))
        painter.drawLine(0, 0, 180, 0)
        painter.setPen(QPen(QColor(theme.ACCENT_GLOW), 1.0))
        painter.drawLine(180, 0, 240, 0)

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 6, 14, 6)
        root.setSpacing(10)

        # Title Card (Chamfered MechPanel)
        self.title_panel = MechPanel(self, chamfer=8, style='diagonal', bg_color='#101624', border_color=theme.BORDER)
        t_layout = QHBoxLayout(self.title_panel)
        t_layout.setContentsMargins(12, 4, 14, 4)
        t_layout.setSpacing(10)

        self.icon_lbl = QLabel(theme.ICON['dashboard'], self.title_panel)
        self.icon_lbl.setFont(theme.qfont('Segoe UI Symbol', 18, True))
        self.icon_lbl.setStyleSheet('color: %s;' % theme.ACCENT)
        t_layout.addWidget(self.icon_lbl)

        txt = QFrame(self.title_panel)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.title_lbl = QLabel('Dashboard', txt)
        self.title_lbl.setFont(theme.qfont(theme.FONT_FAMILY, 10, True))
        self.title_lbl.setStyleSheet('color: %s;' % theme.FG)
        v.addWidget(self.title_lbl)
        self.sub_lbl = QLabel('Live HUD Telemetry & Automation', txt)
        self.sub_lbl.setFont(theme.qfont(theme.FONT_MONO, 7))
        self.sub_lbl.setStyleSheet('color: %s;' % theme.FG_MUTED)
        v.addWidget(self.sub_lbl)
        t_layout.addWidget(txt)
        root.addWidget(self.title_panel)

        root.addStretch(1)

        # Resolution Badge (Chamfered MechPanel)
        self.size_panel = MechPanel(self, chamfer=6, style='diagonal', bg_color='#101826', border_color=theme.ACCENT)
        s_layout = QHBoxLayout(self.size_panel)
        s_layout.setContentsMargins(8, 4, 8, 4)
        self.size_lbl = QLabel('RESOLUTION: 960x620', self.size_panel)
        self.size_lbl.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        self.size_lbl.setStyleSheet('color: %s;' % theme.ACCENT)
        s_layout.addWidget(self.size_lbl)
        root.addWidget(self.size_panel)

    def set_page(self, page):
        title, sub, icon = PAGES.get(page, (page, '', '\u25C8'))
        self.title_lbl.setText(title)
        self.sub_lbl.setText(sub)
        self.icon_lbl.setText(icon)

    def set_size(self, w, h):
        self.size_lbl.setText('RESOLUTION: %dx%d' % (w, h))
