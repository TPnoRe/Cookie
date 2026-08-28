"""About — ข้อมูลระบบและสถาปัตยกรรมหุ่นยนต์ Mech Edition (PyQt6)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout
)
from ui import theme


class About(QFrame):
    """หน้าข้อมูล Mech Protocol & Diagnostics."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        card = QFrame(self)
        card.setObjectName('hudCard')
        card.setStyleSheet('QFrame#hudCard { background: #111722; border: 1px solid %s; border-radius: 8px; }' % theme.BORDER)
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)

        t = QLabel('COOKIE RUN BOT // MECH EDITION v2.1', card)
        t.setFont(theme.qfont(theme.FONT_FAMILY, 13, True))
        t.setStyleSheet('color: %s;' % theme.ACCENT)
        v.addWidget(t)

        sub = QLabel('Tactical Mecha HUD Automation & Optical Neural Target Tracking Platform.', card)
        sub.setFont(theme.qfont(theme.FONT_FAMILY, 9))
        sub.setStyleSheet('color: %s;' % theme.FG_DIM)
        v.addWidget(sub)

        sep = QFrame(card)
        sep.setFixedHeight(1)
        sep.setStyleSheet('background: %s;' % theme.BORDER)
        v.addWidget(sep)

        details = [
            ('ENGINE VERSION', 'MECH-CORE 2.1.0-STABLE'),
            ('UI FRAMEWORK', 'PyQt6 GPU-Accelerated Fusion HUD'),
            ('VISION PROCESSOR', 'OpenCV High-Speed Template Matching + OCR Matrix'),
            ('EMULATOR BRIDGE', 'ADB Protocol / Subsystem Touch Stream (60 FPS)'),
            ('OPERATIONAL STATUS', 'SYSTEM NORMAL // 100% CALIBRATED'),
        ]
        for k, val in details:
            h = QHBoxLayout()
            lk = QLabel(k, card)
            lk.setFont(theme.qfont(theme.FONT_MONO, 8, True))
            lk.setStyleSheet('color: %s;' % theme.FG_MUTED)
            lk.setFixedWidth(160)
            h.addWidget(lk)

            lv = QLabel(val, card)
            lv.setFont(theme.qfont(theme.FONT_MONO, 8, True))
            lv.setStyleSheet('color: %s;' % (theme.GREEN if 'STATUS' in k else theme.FG))
            h.addWidget(lv)
            h.addStretch(1)
            v.addLayout(h)

        root.addWidget(card, 1)
