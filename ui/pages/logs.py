"""Logs — หน้าต่างบันทึกกิจกรรมคอนโซล สไตล์ Sci-Fi Terminal (PyQt6)."""
import time
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ui import theme


class Logs(QFrame):
    """หน้าต่างแสดง Activity Logs แบบ Full Screen Terminal."""

    MAX_LOG = 300

    LOG_COLORS = {
        'info': theme.FG_MUTED,
        'ok': theme.GREEN,
        'warn': theme.AMBER,
        'err': theme.RED,
    }

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._log_entries = []
        self._active_filter = 'ALL'
        self._filter_buttons = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header Bar
        card = QFrame(self)
        card.setObjectName('hudCard')
        card.setStyleSheet('QFrame#hudCard { background: #111722; border: 1px solid %s; border-radius: 8px; }' % theme.BORDER)
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        top_bar = QHBoxLayout()
        lbl = QLabel('// TERMINAL EVENT TELEMETRY', card)
        lbl.setFont(theme.qfont(theme.FONT_MONO, 10, True))
        lbl.setStyleSheet('color: %s;' % theme.ACCENT)
        top_bar.addWidget(lbl)
        top_bar.addStretch(1)

        for level in ('ALL', 'INFO', 'OK', 'WARN', 'ERR'):
            btn = QPushButton(level, card)
            btn.setProperty('btn', 'filter')
            btn.setFont(theme.qfont(theme.FONT_MONO, 8, True))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, l=level: self._set_filter(l))
            top_bar.addWidget(btn)
            self._filter_buttons[level] = btn

        btn_clear = QPushButton('CLEAR LOG', card)
        btn_clear.setProperty('btn', 'danger')
        btn_clear.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_log)
        top_bar.addWidget(btn_clear)

        v.addLayout(top_bar)

        self.log_box = QPlainTextEdit(card)
        self.log_box.setReadOnly(True)
        self.log_box.setFont(theme.qfont(theme.FONT_MONO, 9))
        self.log_box.setMaximumBlockCount(self.MAX_LOG)
        self.log_box.setStyleSheet(
            'QPlainTextEdit { background: #0A0D14; border: 1px solid %s; border-radius: 6px; padding: 8px; color: %s; }'
            % (theme.BORDER, theme.FG)
        )
        v.addWidget(self.log_box, 1)

        root.addWidget(card, 1)
        self._style_filters()


    def _set_filter(self, level):
        self._active_filter = level
        self._style_filters()
        self._render_logs()

    def _style_filters(self):
        for lvl, btn in self._filter_buttons.items():
            active = lvl == self._active_filter
            btn.setProperty('active', active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def push_log(self, level, message):
        ts = time.strftime('%H:%M:%S')
        self._log_entries.append((level, ts, message))
        self._render_logs()

    def clear_log(self):
        self._log_entries.clear()
        self._render_logs()

    def _render_logs(self):
        self.log_box.clear()
        filtered = [
            e for e in self._log_entries
            if self._active_filter == 'ALL' or self._is_match(e[0])
        ]
        for level, ts, msg in filtered[-150:]:
            ts_fmt = QTextCharFormat()
            ts_fmt.setForeground(QColor(theme.ACCENT))
            msg_fmt = QTextCharFormat()
            msg_fmt.setForeground(
                QColor(self.LOG_COLORS.get(level, theme.FG)))
            cursor = self.log_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_box.setTextCursor(cursor)
            self.log_box.setCurrentCharFormat(ts_fmt)
            self.log_box.insertPlainText('[%s] ' % ts)
            self.log_box.setCurrentCharFormat(msg_fmt)
            self.log_box.insertPlainText('%s\n' % msg)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _is_match(self, level):
        if self._active_filter == 'ALL':
            return True
        return level == self._active_filter.lower()
