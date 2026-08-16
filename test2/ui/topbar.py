"""TopBar — แถบหัวข้อหน้า ด้านบนขวา (แสดงชื่อหน้า + ขนาดหน้าต่าง) (PyQt6)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui import theme

PAGES = {
    'dashboard': ('Dashboard', 'Control bot & monitor live', theme.ICON['dashboard']),
    'settings': ('Settings', 'Bot engine configurations', theme.ICON['settings']),
    'coordinates': ('Coordinates', 'Manage tap targets', theme.ICON['coordinates']),
}


class TopBar(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.setFixedHeight(52)
        self.setStyleSheet('TopBar { background: %s; }' % theme.BG)
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 0, 16, 0)
        root.setSpacing(8)

        self.icon_lbl = QLabel(theme.ICON['dashboard'], self)
        self.icon_lbl.setFont(theme.qfont(theme.FONT_FAMILY, 15, True))
        self.icon_lbl.setStyleSheet('color: %s;' % theme.ACCENT)
        self.icon_lbl.setFixedWidth(26)
        root.addWidget(self.icon_lbl)

        txt = QFrame(self)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.title_lbl = QLabel('Dashboard', txt)
        self.title_lbl.setFont(theme.qfont(*theme.TITLE_FONT))
        v.addWidget(self.title_lbl)
        self.sub_lbl = QLabel('Control bot & monitor live', txt)
        self.sub_lbl.setFont(theme.qfont(*theme.SUBTITLE_FONT))
        self.sub_lbl.setProperty('role', 'muted')
        v.addWidget(self.sub_lbl)
        root.addWidget(txt)

        root.addStretch(1)

        self.size_lbl = QLabel('\u25A1  800 x 600', self)
        self.size_lbl.setFont(theme.qfont(*theme.XS_FONT))
        self.size_lbl.setProperty('role', 'muted')
        self.size_lbl.setStyleSheet(
            'QLabel { background: %s; border-radius: 6px;'
            ' padding: 2px 8px; }' % theme.BG_CARD)
        self.size_lbl.setFixedWidth(96)
        root.addWidget(self.size_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_page(self, page):
        title, sub, icon = PAGES.get(page, (page, '', '\u25C8'))
        self.title_lbl.setText(title)
        self.sub_lbl.setText(sub)
        self.icon_lbl.setText(icon)

    def set_size(self, w, h):
        self.size_lbl.setText('\u25A1  %d x %d' % (w, h))
