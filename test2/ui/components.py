"""Components — widget สำเร็จรูปสำหรับสร้างหน้า UI ให้เป็นแบบเดียวกัน (PyQt6)."""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout,
    QDialog, QPushButton, QGraphicsOpacityEffect,
)

from ui import theme


def card(parent, title=None, icon=None, **kw):
    frame = QFrame(parent)
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if title:
        header = QFrame(frame)
        header.setObjectName('cardHeader')
        header.setFixedHeight(34)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 4)
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
