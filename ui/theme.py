"""Theme — สี / ฟอนต์ / ขนาดกลางของโปรแกรม (Cookie Run Bot: Robotic Mech Edition, PyQt6)."""
from PyQt6.QtCore import Qt, QSize, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QColor, QPalette, QPen, QBrush
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

# ── Robotic Mecha Palette ────────────────────────────────
BG            = '#0B0E14'   # Deep Cyber Gunmetal
BG_SIDEBAR    = '#0E121B'   # Dark Mecha Subsystem Panel
BG_CARD       = '#131924'   # HUD Tactical Card
BG_CARD_HOVER = '#1B2434'
BG_INPUT      = '#172030'
BG_INPUT_FOCUS= '#202C42'

BORDER        = '#1E2B3E'
BORDER_ACTIVE = '#00F0FF'
BORDER_AMBER  = '#FFAE00'

ACCENT        = '#00F0FF'   # Electric Cyan Neon
ACCENT_DEEP   = '#0099B8'
ACCENT_GLOW   = '#38BDF8'
ACCENT_SOFT   = '#0F2C3D'

AMBER         = '#FFAE00'   # Hazard Amber
AMBER_DEEP    = '#D97706'
AMBER_SOFT    = '#3B2910'

PURPLE        = '#A855F7'
PURPLE_GLOW   = '#C084FC'

GREEN         = '#00FF9D'   # Matrix Emerald / System Online
GREEN_BG      = '#0A2E20'
RED           = '#FF3366'   # Crimson Overload / Abort
RED_BG        = '#38101E'
BLUE          = '#00C2FF'
ORANGE        = '#FF9F1C'
YELLOW        = '#FFD166'

FG            = '#F0F4FC'
FG_DIM        = '#94A3B8'
FG_MUTED      = '#5B6E88'

# ── Fonts ────────────────────────────────────────────────
FONT_FAMILY = 'Segoe UI'
FONT_MONO   = 'Consolas'

LOGO_FONT      = (FONT_FAMILY, 12, 'bold')
NAV_FONT       = (FONT_FAMILY, 10)
NAV_FONT_ACTIVE= (FONT_FAMILY, 10, 'bold')
TITLE_FONT     = (FONT_FAMILY, 13, 'bold')
SUBTITLE_FONT  = (FONT_FAMILY, 9)
SECTION_FONT   = (FONT_FAMILY, 10, 'bold')
BODY_FONT      = (FONT_FAMILY, 10)
SMALL_FONT     = (FONT_FAMILY, 9)
XS_FONT        = (FONT_FAMILY, 8)
MONO_FONT      = (FONT_MONO, 9)
BTN_FONT       = (FONT_FAMILY, 10, 'bold')
STAT_NUM_FONT  = (FONT_MONO, 15, 'bold')
STAT_LABEL_FONT= (FONT_FAMILY, 8)

# ── Icons (Unicode) ──────────────────────────────────────
ICON = {
    'logo':       '\u2B21',    # ⬡ Hexagon Core
    'dashboard':  '\u229E',    # ⊞ HUD Grid
    'settings':   '\u2699',    # ⚙ Gear
    'coordinates':'\u2316',    # ⌖ Target Reticle
    'profile':    '\uD83D\uDC64', # 👤 Profile
    'logs':       '\uD83D\uDCDD', # 📝 Logs
    'diag':       '\uD83D\uDD27', # 🔧 Diagnostics
    'about':      '\u2139',    # ℹ About
    'camera':     '\u25C8',
    'play':       '\u25B6',
    'stop':       '\u25A0',
    'pause':      '\u23F8',
    'pulse':      '\u2668',
    'check':      '\u2713',
    'x':          '\u2715',
    'plus':       '\uFF0B',
    'edit':       '\u270E',
    'trash':      '\u00D7',
    'arrow':      '\u203A',
}


def qfont(name=None, size=None, bold=False):
    """สร้าง QFont จาก tuple/ค่าตรง (รับ format แบบ theme.*_FONT ด้วย)."""
    if isinstance(name, tuple):
        fam, sz, *rest = name
        return qfont(fam, sz, bold=bool(rest and rest[0] == 'bold'))
    f = QFont(name or FONT_FAMILY)
    if size:
        f.setPointSize(size)
    f.setBold(bold is True or bold == 'bold')
    return f


def app_style():
    """QSS ทั้งหมดของแอป — สไตล์ Sci-Fi Futuristic Mecha HUD."""
    return '''
* {
    font-family: "Segoe UI";
    font-size: 10pt;
    color: %(FG)s;
}
QMainWindow, QWidget#root {
    background: %(BG)s;
}
QFrame#card {
    background: %(BG_CARD)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
}
QFrame#hudCard {
    background: %(BG_CARD)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
}
QFrame#cardHeader {
    background: transparent;
    border: none;
}
QFrame#transparent {
    background: transparent;
    border: none;
}
QFrame[sep="true"] {
    background: %(BORDER)s;
    border: none;
}
QLabel {
    background: transparent;
}
QLabel[role="section"] {
    color: %(ACCENT)s;
    font-weight: bold;
    font-size: 10pt;
}
QLabel[role="muted"] {
    color: %(FG_MUTED)s;
}
QLabel[role="dim"] {
    color: %(FG_DIM)s;
}
QLabel[role="glow"] {
    color: %(ACCENT)s;
}
QLabel[role="amber"] {
    color: %(AMBER)s;
}
QLabel[role="green"] {
    color: %(GREEN)s;
}
QPushButton {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background: %(BG_CARD_HOVER)s;
    border-color: %(ACCENT_DEEP)s;
    color: #FFFFFF;
}
QPushButton:pressed {
    background: %(BG_INPUT_FOCUS)s;
    border-color: %(ACCENT)s;
}
QPushButton:disabled {
    color: %(FG_MUTED)s;
    background: %(BG_CARD)s;
    border-color: %(BORDER)s;
}
QPushButton[btn="primary"] {
    background: %(ACCENT)s;
    color: #0B0E14;
    border: 1px solid %(ACCENT_GLOW)s;
    font-weight: bold;
}
QPushButton[btn="primary"]:hover {
    background: %(ACCENT_GLOW)s;
    color: #000000;
}
QPushButton[btn="engage"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0B2533, stop:0.5 #103444, stop:1 #0B2533);
    color: #00F0FF;
    border: 2px solid #00F0FF;
    border-radius: 10px;
    font-size: 12pt;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 18px;
}
QPushButton[btn="engage"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00F0FF, stop:0.5 #38BDF8, stop:1 #00F0FF);
    color: #0B0E14;
    border-color: #FFFFFF;
}
QPushButton[btn="engage-running"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3D101C, stop:0.5 #5C182B, stop:1 #3D101C);
    color: #FF3366;
    border: 2px solid #FF3366;
    border-radius: 10px;
    font-size: 12pt;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 18px;
}
QPushButton[btn="engage-running"]:hover {
    background: #FF3366;
    color: #FFFFFF;
}
QPushButton[btn="amber"] {
    background: %(AMBER_SOFT)s;
    color: %(AMBER)s;
    border: 1px solid %(AMBER)s;
    font-weight: bold;
}
QPushButton[btn="amber"]:hover {
    background: %(AMBER)s;
    color: #0B0E14;
}
QPushButton[btn="dark"] {
    background: #172030;
    color: %(FG_DIM)s;
    border: 1px solid %(BORDER)s;
}
QPushButton[btn="dark"]:hover {
    background: %(BG_CARD_HOVER)s;
    color: #FFFFFF;
    border-color: %(ACCENT_DEEP)s;
}
QPushButton[btn="info"] {
    background: #0F2C3D;
    color: %(ACCENT)s;
    border: 1px solid %(ACCENT_DEEP)s;
}
QPushButton[btn="info"]:hover {
    background: #164058;
}
QPushButton[btn="danger"] {
    background: %(RED_BG)s;
    color: %(RED)s;
    border: 1px solid %(RED)s;
}
QPushButton[btn="danger"]:hover {
    background: %(RED)s;
    color: #FFFFFF;
}
QPushButton[btn="success"] {
    background: %(GREEN_BG)s;
    color: %(GREEN)s;
    border: 1px solid %(GREEN)s;
    font-weight: bold;
}
QPushButton[btn="success"]:hover {
    background: %(GREEN)s;
    color: #0B0E14;
}
QPushButton[btn="ghost"] {
    background: transparent;
    color: %(FG_DIM)s;
    border: none;
}
QPushButton[btn="ghost"]:hover {
    background: %(BG_CARD_HOVER)s;
    color: %(FG)s;
}
QPushButton[btn="nav"] {
    background: transparent;
    color: %(FG_DIM)s;
    text-align: left;
    padding: 9px 14px;
    border-radius: 7px;
    border: 1px solid transparent;
}
QPushButton[btn="nav"]:hover {
    background: %(BG_CARD_HOVER)s;
    color: %(FG)s;
    border-color: %(BORDER)s;
}
QPushButton[btn="nav"][active="true"] {
    background: %(ACCENT_SOFT)s;
    color: %(ACCENT)s;
    border: 1px solid %(ACCENT)s;
    font-weight: bold;
}
QPushButton[btn="filter"] {
    background: transparent;
    color: %(FG_MUTED)s;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 10px;
}
QPushButton[btn="filter"]:hover {
    background: %(BG_CARD_HOVER)s;
    color: %(FG)s;
}
QPushButton[btn="filter"][active="true"] {
    background: %(ACCENT_SOFT)s;
    color: %(ACCENT)s;
    border: 1px solid %(ACCENT)s;
}
QPushButton[btn="seg"] {
    background: %(BG_INPUT)s;
    color: %(FG_DIM)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 4px 12px;
}
QPushButton[btn="seg"][active="true"] {
    background: %(ACCENT)s;
    color: #0B0E14;
    border-color: %(ACCENT_GLOW)s;
    font-weight: bold;
}
QFrame#stageSeg {
    background: transparent;
    border: none;
}
QFrame#stageSeg QPushButton {
    background: transparent;
    color: %(FG_DIM)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 5px 0;
    font-weight: bold;
}
QFrame#stageSeg QPushButton:hover {
    background: %(BG_CARD_HOVER)s;
}
QFrame#stageSeg QPushButton[active="true"] {
    background: %(ACCENT)s;
    color: #0B0E14;
    border-color: %(ACCENT)s;
}
QLineEdit {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 4px 8px;
    font-family: "Consolas", "Segoe UI";
    selection-background-color: %(ACCENT_DEEP)s;
}
QLineEdit:focus {
    border: 1px solid %(ACCENT)s;
}
QComboBox {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 6px 10px 6px 12px;
    padding-right: 30px;
}
QComboBox:hover { border-color: %(ACCENT)s; }
QComboBox:on {
    border: 1px solid %(ACCENT)s;
}
QComboBox QAbstractItemView {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: transparent;
    selection-color: transparent;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 24px;
    background: transparent;
    border: none;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: url("data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%%3E%%3Cpath d='M3 5l3 3 3-3' fill='none' stroke='%%2300F0FF' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%%3E%%3C/svg%%3E");
    width: 12px;
    height: 12px;
    margin-right: 8px;
}
QCheckBox {
    background: transparent;
    color: %(FG)s;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid %(BORDER)s;
    border-radius: 4px;
    background: %(BG_INPUT)s;
}
QCheckBox::indicator:hover { border-color: %(ACCENT)s; }
QCheckBox::indicator:checked {
    background: %(ACCENT)s;
    border: 1px solid %(ACCENT)s;
    image: none;
}
QCheckBox::indicator:checked { background-color: %(ACCENT)s; }
QPlainTextEdit, QTextEdit {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    font-family: "Consolas", monospace;
    selection-background-color: %(ACCENT_DEEP)s;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid %(ACCENT)s;
}
QProgressBar {
    background: %(BG_INPUT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 4px;
    text-align: center;
    color: %(FG)s;
    font-size: 8pt;
    font-weight: bold;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(ACCENT_DEEP)s, stop:1 %(ACCENT)s);
    border-radius: 3px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: %(BG)s;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: %(BORDER)s;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: %(ACCENT_DEEP)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: %(BG)s;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: %(BORDER)s;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
''' % {
    'BG': BG, 'BG_SIDEBAR': BG_SIDEBAR, 'BG_CARD': BG_CARD,
    'BG_CARD_HOVER': BG_CARD_HOVER, 'BG_INPUT': BG_INPUT,
    'BG_INPUT_FOCUS': BG_INPUT_FOCUS, 'BORDER': BORDER,
    'ACCENT': ACCENT, 'ACCENT_DEEP': ACCENT_DEEP,
    'ACCENT_GLOW': ACCENT_GLOW, 'ACCENT_SOFT': ACCENT_SOFT,
    'AMBER': AMBER, 'AMBER_SOFT': AMBER_SOFT,
    'GREEN': GREEN, 'GREEN_BG': GREEN_BG,
    'RED': RED, 'RED_BG': RED_BG, 'BLUE': BLUE,
    'FG': FG, 'FG_DIM': FG_DIM, 'FG_MUTED': FG_MUTED,
}


class HoverDelegate(QStyledItemDelegate):
    """Custom delegate for dropdown hover highlight."""

    def __init__(self, combo=None, parent=None):
        super().__init__(parent)
        self._combo = combo

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 1, -2, -1)
        is_hover = option.state & QStyle.StateFlag.State_MouseOver
        is_selected = (self._combo is not None and
                       index.row() == self._combo.currentIndex())
        if is_hover or is_selected:
            painter.setBrush(QColor(BG_INPUT_FOCUS))
            painter.setPen(QPen(QColor(ACCENT_DEEP), 1))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QPen(QColor(FG)))
            if is_selected:
                check_rect = rect.adjusted(rect.width() - 28, 0, -6, 0)
                painter.drawText(check_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, '✓')
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            painter.setPen(QPen(QColor(FG)))
        text = index.data(Qt.ItemDataRole.DisplayRole) or ''
        painter.drawText(rect.adjusted(10, 0, -8, 0),
                         Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(0, 28)


def install_hover(combo):
    """Install HoverDelegate on a QComboBox for proper hover highlight."""
    combo.setItemDelegate(HoverDelegate(combo, combo))


def dropdown_style():
    """QSS สำหรับ custom Dropdown widget."""
    return '''
QFrame#dropdownTrigger {
    background: %(BG_INPUT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
}
QFrame#dropdownTrigger:hover {
    border-color: %(ACCENT)s;
}
QFrame#dropdownMenu {
    background: %(BG_INPUT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 0 0 6px 6px;
    border-top: none;
}
QFrame#dropdownMenu QScrollArea {
    background: transparent;
    border: none;
}
QFrame#dropdownMenu QScrollArea > QWidget > QWidget {
    background: transparent;
}
QFrame#dropdownMenu QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QFrame#dropdownMenu QScrollBar::handle:vertical {
    background: %(BORDER)s;
    border-radius: 3px;
    min-height: 16px;
}
QFrame#dropdownMenu QScrollBar::handle:vertical:hover {
    background: %(ACCENT_DEEP)s;
}
QFrame#dropdownMenu QScrollBar::add-line:vertical,
QFrame#dropdownMenu QScrollBar::sub-line:vertical {
    height: 0;
}
QFrame#dropdownSearchBox {
    background: transparent;
    border: none;
}
QLineEdit {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 4px 8px;
}
QLineEdit:focus {
    border: 1px solid %(ACCENT)s;
}
''' % {
    'BG_INPUT': BG_INPUT, 'BORDER': BORDER,
    'ACCENT': ACCENT, 'ACCENT_DEEP': ACCENT_DEEP,
    'FG': FG, 'FG_MUTED': FG_MUTED,
}
