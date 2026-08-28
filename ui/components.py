"""Components — widget สำเร็จรูปสไตล์ Robotic Mech HUD (PyQt6).

มีกรอบรูปทรงแปดเหลี่ยมตัดมุม 45 องศา (Chamfered Polygons) และปุ่มทรงค็อกพิทจักรกล.
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QLinearGradient, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout,
    QDialog, QPushButton, QGraphicsOpacityEffect, QWidget
)

from ui import theme


class MechPanel(QFrame):
    """กรอบการ์ดสไตล์ Sci-Fi Mecha ตัดมุมเฉียง 45 องศา (Chamfered Non-Rectangular Polygon)."""

    def __init__(self, parent=None, chamfer=12, style='diagonal', border_color=None, bg_color='#111724', glow=False):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.chamfer = chamfer
        self.style = style  # 'diagonal', 'all', 'cockpit'
        self.border_color = border_color or theme.BORDER
        self.bg_color = bg_color
        self.glow = glow

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() - 1
        h = self.height() - 1
        c = self.chamfer

        path = QPainterPath()
        if self.style == 'all':
            # Cut all 4 corners
            path.moveTo(c, 0)
            path.lineTo(w - c, 0)
            path.lineTo(w, c)
            path.lineTo(w, h - c)
            path.lineTo(w - c, h)
            path.lineTo(c, h)
            path.lineTo(0, h - c)
            path.lineTo(0, c)
            path.closeSubpath()
        elif self.style == 'diagonal':
            # Cut Top-Left & Bottom-Right
            path.moveTo(c, 0)
            path.lineTo(w, 0)
            path.lineTo(w, h - c)
            path.lineTo(w - c, h)
            path.lineTo(0, h)
            path.lineTo(0, c)
            path.closeSubpath()
        elif self.style == 'cockpit':
            # Futuristic Cockpit Frame with Header Notch
            notch_w = min(120, int(w * 0.35))
            notch_h = 6
            path.moveTo(c, 0)
            path.lineTo(int(w / 2 - notch_w / 2), 0)
            path.lineTo(int(w / 2 - notch_w / 2 + notch_h), notch_h)
            path.lineTo(int(w / 2 + notch_w / 2 - notch_h), notch_h)
            path.lineTo(int(w / 2 + notch_w / 2), 0)
            path.lineTo(w - c, 0)
            path.lineTo(w, c)
            path.lineTo(w, h - c)
            path.lineTo(w - c, h)
            path.lineTo(c, h)
            path.lineTo(0, h - c)
            path.lineTo(0, c)
            path.closeSubpath()
        else:
            path.moveTo(c, 0)
            path.lineTo(w - c, 0)
            path.lineTo(w, c)
            path.lineTo(w, h - c)
            path.lineTo(w - c, h)
            path.lineTo(c, h)
            path.lineTo(0, h - c)
            path.lineTo(0, c)
            path.closeSubpath()

        # Fill background
        painter.setBrush(QColor(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Draw main border
        border_pen = QPen(QColor(self.border_color), 1.2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Corner Accent Highlights
        accent_pen = QPen(QColor(theme.ACCENT), 2)
        painter.setPen(accent_pen)
        painter.drawLine(0, c, c, 0)
        if self.style in ('all', 'diagonal', 'cockpit'):
            painter.drawLine(w, h - c, w - c, h)

        if self.glow:
            painter.setPen(QPen(QColor(theme.ACCENT_GLOW), 1.5))
            painter.drawLine(c + 4, 0, min(w - c, c + 28), 0)


class MechButton(QPushButton):
    """ปุ่มกดตัดมุมเฉียงสไตล์หุ่นยนต์ Mecha (Chamfered Action Button)."""

    def __init__(self, text="", parent=None, chamfer=10, btn_type='primary'):
        super().__init__(text, parent)
        self.chamfer = chamfer
        self.btn_type = btn_type  # 'engage', 'engage-running', 'primary', 'dark', 'amber'
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_btn_type(self, btn_type):
        self.btn_type = btn_type
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width() - 1
        h = self.height() - 1
        c = self.chamfer

        path = QPainterPath()
        path.moveTo(c, 0)
        path.lineTo(w - c, 0)
        path.lineTo(w, c)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(c, h)
        path.lineTo(0, h - c)
        path.lineTo(0, c)
        path.closeSubpath()

        is_hover = self.underMouse() and self.isEnabled()

        if self.btn_type == 'engage':
            if is_hover:
                bg_col1 = QColor('#00F0FF')
                bg_col2 = QColor('#0284C7')
                border_col = QColor('#FFFFFF')
                text_col = QColor('#0B0E14')
            else:
                bg_col1 = QColor('#0B2533')
                bg_col2 = QColor('#103848')
                border_col = QColor('#00F0FF')
                text_col = QColor('#00F0FF')
        elif self.btn_type == 'engage-running':
            if is_hover:
                bg_col1 = QColor('#FF3366')
                bg_col2 = QColor('#DC2626')
                border_col = QColor('#FFFFFF')
                text_col = QColor('#FFFFFF')
            else:
                bg_col1 = QColor('#3D101C')
                bg_col2 = QColor('#5C182B')
                border_col = QColor('#FF3366')
                text_col = QColor('#FF3366')
        elif self.btn_type == 'amber':
            bg_col1 = QColor('#FFAE00' if is_hover else '#3B2910')
            bg_col2 = bg_col1
            border_col = QColor('#FFAE00')
            text_col = QColor('#0B0E14' if is_hover else '#FFAE00')
        else:
            bg_col1 = QColor('#1E2A3E' if is_hover else '#131C2A')
            bg_col2 = bg_col1
            border_col = QColor(theme.ACCENT if is_hover else theme.BORDER)
            text_col = QColor('#FFFFFF' if is_hover else theme.FG_DIM)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, bg_col1)
        grad.setColorAt(1.0, bg_col2)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        bpen = QPen(border_col, 2.0 if 'engage' in self.btn_type else 1.2)
        painter.setPen(bpen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if 'engage' in self.btn_type:
            painter.setPen(QPen(QColor(theme.ACCENT_GLOW if self.btn_type == 'engage' else theme.RED), 2.5))
            painter.drawLine(0, c, c, 0)
            painter.drawLine(w, h - c, w - c, h)

        painter.setPen(text_col)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


def card(parent, title=None, icon=None, **kw):
    frame = MechPanel(parent, chamfer=10, style='diagonal', bg_color=theme.BG_CARD)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    if title:
        header = QFrame(frame)
        header.setObjectName('cardHeader')
        header.setFixedHeight(28)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(6)
        icon_lbl = QLabel(icon + '  ' if icon else '', header)
        icon_lbl.setProperty('role', 'section')
        icon_lbl.setFont(theme.qfont(*theme.SECTION_FONT))
        h_layout.addWidget(icon_lbl)
        title_lbl = QLabel(title, header)
        title_lbl.setFont(theme.qfont(*theme.SECTION_FONT))
        title_lbl.setProperty('role', 'section')
        h_layout.addWidget(title_lbl)
        h_layout.addStretch(1)
        layout.addWidget(header)
    return frame


def label(parent, text, **kw):
    lbl = QLabel(text, parent)
    lbl.setFont(theme.qfont(*theme.BODY_FONT))
    return lbl


def hint(parent, text, **kw):
    lbl = QLabel(text, parent)
    lbl.setFont(theme.qfont(*theme.XS_FONT))
    lbl.setProperty('role', 'muted')
    return lbl


class Toast(QFrame):
    """popup แจ้งเตือนแบบ toast (แสดงที่มุมขวาล่าง, หายเอง)."""

    COLORS = {
        'ok':     (theme.GREEN,  '\u2713  '),
        'warn':   (theme.ACCENT, '\u26a0  '),
        'error':  ('#e53935',    '\u2717  '),
        'info':   (theme.FG,     '\u2139  '),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('toast')
        self.setFixedWidth(340)
        self.setFixedHeight(50)
        try:
            self.hide()
        except (RuntimeError, Exception):
            pass

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(8)

        self._icon_lbl = QLabel('', self)
        self._icon_lbl.setFont(theme.qfont(*theme.BTN_FONT))
        h.addWidget(self._icon_lbl)

        self._text_lbl = QLabel('', self)
        self._text_lbl.setFont(theme.qfont(*theme.SMALL_FONT))
        self._text_lbl.setWordWrap(True)
        h.addWidget(self._text_lbl, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._safe_hide)

        self._destroyed = False

    def show_toast(self, level, text, duration=3000):
        try:
            if self._destroyed:
                return
            try:
                self._timer.stop()
            except (RuntimeError, Exception):
                pass

            color, icon = self.COLORS.get(level, self.COLORS['info'])
            self._icon_lbl.setText(icon)
            self._icon_lbl.setStyleSheet('color: %s; background: transparent;' % color)
            self._text_lbl.setText(text)
            self._text_lbl.setStyleSheet('color: %s; background: transparent;' % theme.FG)
            self.setStyleSheet(
                'QFrame#toast { background: %s; border-radius: 8px;'
                ' border: 1px solid %s; }' % (theme.BG_CARD, color))
            self.raise_()
            self.show()
            self._position()
            self._timer.start(duration)
        except (RuntimeError, Exception):
            pass

    def _position(self):
        try:
            if self._destroyed:
                return
            p = self.parent()
            if p:
                pw = p.width()
                self.move(pw - self.width() - 12, 12)
        except (RuntimeError, Exception):
            pass

    def _safe_hide(self):
        try:
            if self._destroyed:
                return
            self.hide()
        except (RuntimeError, Exception):
            pass

    def _fade_out(self):
        self._safe_hide()

    def closeEvent(self, event):
        try:
            self._destroyed = True
            try:
                self._timer.stop()
            except (RuntimeError, Exception):
                pass
            super().closeEvent(event)
        except (RuntimeError, Exception):
            pass


class ConfirmDialog(QDialog):
    """Modal dialog ยืนยัน."""

    def __init__(self, parent, title, message, confirm_text='Confirm',
                 level='warn'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(380, 180)
        self.setStyleSheet(
            'QDialog { background: %s; }' % theme.BG_CARD)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 14)
        v.setSpacing(10)

        colors = {'ok': theme.GREEN, 'warn': theme.ACCENT, 'error': '#e53935'}
        icons = {'ok': '\u2713', 'warn': '\u26a0', 'error': '\u2717'}
        color = colors.get(level, theme.ACCENT)
        icon = icons.get(level, '\u26a0')

        head = QHBoxLayout()
        head.setSpacing(10)
        icon_lbl = QLabel(icon, self)
        icon_lbl.setFont(theme.qfont(*theme.BTN_FONT))
        icon_lbl.setStyleSheet('color: %s; background: transparent;' % color)
        head.addWidget(icon_lbl)
        msg_lbl = QLabel(message, self)
        msg_lbl.setFont(theme.qfont(*theme.SMALL_FONT))
        msg_lbl.setStyleSheet('color: %s; background: transparent;' % theme.FG)
        msg_lbl.setWordWrap(True)
        head.addWidget(msg_lbl, 1)
        v.addLayout(head)

        v.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_cancel = QPushButton('Cancel', self)
        btn_cancel.setFont(theme.qfont(*theme.SMALL_FONT))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setFixedWidth(90)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_confirm = QPushButton(confirm_text, self)
        btn_confirm.setProperty('btn', 'danger' if level == 'error' else 'primary')
        btn_confirm.setFont(theme.qfont(*theme.SMALL_FONT))
        btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_confirm.setFixedWidth(100)
        btn_confirm.clicked.connect(self.accept)
        btn_row.addWidget(btn_confirm)

        v.addLayout(btn_row)

