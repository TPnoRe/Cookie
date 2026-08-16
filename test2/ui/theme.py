"""Theme — สี / ฟอนต์ / ขนาดกลางของโปรแกรม (Cookie Run Bot, PyQt6)."""
from PyQt6.QtCore import Qt, QSize, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QColor, QPalette, QPen, QBrush
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

# ── Palette ──────────────────────────────────────────────
BG            = '#17181F'
BG_SIDEBAR    = '#12131A'
BG_CARD       = '#1F212B'
BG_CARD_HOVER = '#262935'
BG_INPUT      = '#262935'
BG_INPUT_FOCUS= '#2E3140'

BORDER        = '#2E3140'
BORDER_ACTIVE = '#F5A623'

ACCENT        = '#F5A623'   # สีคุกกี้ทอง
ACCENT_DEEP   = '#C67A1E'
ACCENT_GLOW   = '#F8C14C'
ACCENT_SOFT   = '#3A2E1C'

PURPLE        = '#8B5CF6'
PURPLE_GLOW   = '#A78BFA'

GREEN         = '#22C55E'
GREEN_BG      = '#16301F'
RED           = '#EF4444'
RED_BG        = '#38171A'
BLUE          = '#38BDF8'
ORANGE        = '#F59E0B'
YELLOW        = '#F5C542'

FG            = '#EDEEF4'
FG_DIM        = '#9BA0B4'
FG_MUTED      = '#6A6F85'

# ── Fonts ────────────────────────────────────────────────
FONT_FAMILY = 'Segoe UI'
FONT_MONO   = 'Consolas'

LOGO_FONT      = (FONT_FAMILY, 13, 'bold')
NAV_FONT       = (FONT_FAMILY, 10)
NAV_FONT_ACTIVE= (FONT_FAMILY, 10, 'bold')
TITLE_FONT     = (FONT_FAMILY, 14, 'bold')
SUBTITLE_FONT  = (FONT_FAMILY, 9)
SECTION_FONT   = (FONT_FAMILY, 10, 'bold')
BODY_FONT      = (FONT_FAMILY, 10)
SMALL_FONT     = (FONT_FAMILY, 9)
XS_FONT        = (FONT_FAMILY, 8)
MONO_FONT      = (FONT_MONO, 9)
BTN_FONT       = (FONT_FAMILY, 10, 'bold')
STAT_NUM_FONT  = (FONT_FAMILY, 15, 'bold')
STAT_LABEL_FONT= (FONT_FAMILY, 8)

# ── Icons (Unicode) ──────────────────────────────────────
ICON = {
    'logo':       '\u25CE',
    'dashboard':  '\u2302',
    'settings':   '\u2699',
    'coordinates':'\u2736',
    'camera':     '\u25C8',
    'play':       '\u25B6',
    'stop':       '\u25A0',
    'log':        '\u2630',
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
    """QSS ทั้งหมดของแอป — ธีมมืดทองเดียวกับ CustomTkinter เดิม."""
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
    border-radius: 10px;
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
    color: %(FG_DIM)s;
}
QLabel[role="dim"] {
    color: %(FG_DIM)s;
}
QLabel[role="glow"] {
    color: %(ACCENT_GLOW)s;
}
QPushButton {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: none;
    border-radius: 8px;
    padding: 5px 12px;
}
QPushButton:hover {
    background: %(BG_CARD_HOVER)s;
}
QPushButton:pressed {
    background: %(BG_INPUT_FOCUS)s;
}
QPushButton:disabled {
    color: %(FG_MUTED)s;
    background: %(BG_CARD)s;
}
QPushButton[btn="primary"] {
    background: %(ACCENT)s;
    color: #1A1608;
    font-weight: bold;
}
QPushButton[btn="primary"]:hover { background: %(ACCENT_DEEP)s; }
QPushButton[btn="primary-dark"] {
    background: %(ACCENT_DEEP)s;
    color: #1A1608;
    font-weight: bold;
}
QPushButton[btn="primary-dark"]:hover { background: %(ACCENT)s; }
QPushButton[btn="dark"] {
    background: #252733;
    color: %(FG_DIM)s;
}
QPushButton[btn="dark"]:hover { background: %(BG_CARD_HOVER)s; }
QPushButton[btn="info"] {
    background: #1E3A5F;
    color: %(BLUE)s;
}
QPushButton[btn="info"]:hover { background: #254A73; }
QPushButton[btn="danger"] {
    background: %(RED_BG)s;
    color: %(RED)s;
}
QPushButton[btn="danger"]:hover { background: #4A1A1E; }
QPushButton[btn="success"] {
    background: %(GREEN)s;
    color: #ffffff;
    font-weight: bold;
}
QPushButton[btn="success"]:hover { background: #16A34A; }
QPushButton[btn="ghost"] {
    background: transparent;
    color: %(FG_DIM)s;
}
QPushButton[btn="ghost"]:hover { background: %(BG_CARD_HOVER)s; }
QPushButton[btn="nav"] {
    background: transparent;
    color: %(FG_DIM)s;
    text-align: left;
    padding: 8px 12px;
    border-radius: 8px;
}
QPushButton[btn="nav"]:hover { background: %(BG_CARD_HOVER)s; }
QPushButton[btn="nav"][active="true"] {
    background: %(ACCENT_SOFT)s;
    color: %(ACCENT_GLOW)s;
    font-weight: bold;
}
QPushButton[btn="filter"] {
    background: transparent;
    color: %(FG_MUTED)s;
    border-radius: 6px;
    padding: 3px 10px;
}
QPushButton[btn="filter"]:hover { background: %(BG_CARD_HOVER)s; }
QPushButton[btn="filter"][active="true"] {
    background: %(ACCENT_SOFT)s;
    color: %(ACCENT_GLOW)s;
}
QPushButton[btn="seg"] {
    background: %(BG_INPUT)s;
    color: %(FG_DIM)s;
    border-radius: 6px;
    padding: 4px 12px;
}
QPushButton[btn="seg"][active="true"] {
    background: %(ACCENT)s;
    color: #1A1608;
    font-weight: bold;
}
QFrame#stageSeg {
    background: transparent;
    border: none;
}
QFrame#stageSeg QPushButton {
    background: transparent;
    color: %(FG_DIM)s;
    border: 1px solid %(FG_DIM)s;
    border-radius: 6px;
    padding: 5px 0;
    font-weight: bold;
}
QFrame#stageSeg QPushButton:hover {
    background: %(BG_CARD_HOVER)s;
}
QFrame#stageSeg QPushButton[active="true"] {
    background: %(ACCENT)s;
    color: #1A1608;
    border-color: %(ACCENT_DEEP)s;
}
QLineEdit {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 3px 8px;
    selection-background-color: %(ACCENT_DEEP)s;
}
QLineEdit:focus {
    border: 1px solid %(ACCENT)s;
}
QComboBox {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    padding: 6px 10px 6px 12px;
    padding-right: 30px;
}
QComboBox:hover { border-color: %(ACCENT_DEEP)s; }
QComboBox:on {
    border: 1px solid %(ACCENT)s;
}
QComboBox QAbstractItemView {
    background: %(BG_INPUT)s;
    color: %(FG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    padding: 6px;
    selection-background-color: transparent;
    selection-color: transparent;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 3px;
    min-height: 24px;
    background: transparent;
    border: none;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: url("data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%%3E%%3Cpath d='M3 5l3 3 3-3' fill='none' stroke='%%239BA0B4' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%%3E%%3C/svg%%3E");
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
QCheckBox::indicator:hover { border-color: %(ACCENT_DEEP)s; }
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
    selection-background-color: %(ACCENT_DEEP)s;
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
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: %(BORDER)s;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: %(FG_MUTED)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: %(BG)s;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: %(BORDER)s;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
''' % {
    'BG': BG, 'BG_SIDEBAR': BG_SIDEBAR, 'BG_CARD': BG_CARD,
    'BG_CARD_HOVER': BG_CARD_HOVER, 'BG_INPUT': BG_INPUT,
    'BG_INPUT_FOCUS': BG_INPUT_FOCUS, 'BORDER': BORDER,
    'ACCENT': ACCENT, 'ACCENT_DEEP': ACCENT_DEEP,
    'ACCENT_GLOW': ACCENT_GLOW, 'ACCENT_SOFT': ACCENT_SOFT,
    'GREEN': GREEN, 'RED': RED, 'RED_BG': RED_BG, 'BLUE': BLUE,
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
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRoundedRect(rect, 6, 6)
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
    border-radius: 8px;
}
QFrame#dropdownTrigger:hover {
    border-color: %(ACCENT_DEEP)s;
}
QFrame#dropdownMenu {
    background: %(BG_INPUT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 0 0 8px 8px;
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
    background: %(FG_MUTED)s;
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
