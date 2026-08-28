"""StatusBar — แถบสถานะล่าง (เชื่อมต่อ emulator / ข้อความล่าสุด / เวลา) (PyQt6)."""
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ui import theme


class StatusBar(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setFixedHeight(30)
        self.setStyleSheet(
            'StatusBar { border: 1px solid %s; border-radius: 0; }'
            % theme.BORDER)
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 0, 14, 0)
        root.setSpacing(6)

        self.dot = QLabel('\u25CF', self)
        self.dot.setStyleSheet('color: %s;' % theme.FG_MUTED)
        root.addWidget(self.dot)

        self.status_lbl = QLabel('Emulator disconnected', self)
        self.status_lbl.setFont(theme.qfont(*theme.SMALL_FONT))
        self.status_lbl.setProperty('role', 'muted')
        root.addWidget(self.status_lbl)

        root.addStretch(1)

        self.clock_lbl = QLabel('--:--:--', self)
        self.clock_lbl.setFont(theme.qfont(*theme.MONO_FONT))
        self.clock_lbl.setProperty('role', 'muted')
        root.addWidget(self.clock_lbl)

    def set_status(self, text, color=None):
        try:
            self.status_lbl.setText(text)
            self.dot.setStyleSheet('color: %s;' % (color or theme.FG_MUTED))
            if color:
                self.status_lbl.setStyleSheet('color: %s;' % color)
        except (RuntimeError, Exception):
            pass

    def _tick(self):
        try:
            self.clock_lbl.setText(time.strftime('%H:%M:%S'))
        except (RuntimeError, Exception):
            pass
