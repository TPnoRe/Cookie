"""Profile — หน้านักบิน / ค่าสถิติ Mech Commander (PyQt6)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QProgressBar, QGridLayout, QPushButton
)
from ui import theme


class Profile(QFrame):
    """หน้าข้อมูล Pilot & Mech Matrix."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # Header Profile Card
        hero_card = QFrame(self)
        hero_card.setObjectName('hudCard')
        hero_card.setStyleSheet('QFrame#hudCard { background: #111722; border: 1px solid %s; border-radius: 8px; }' % theme.BORDER)
        h_hero = QHBoxLayout(hero_card)
        h_hero.setContentsMargins(16, 14, 16, 14)
        h_hero.setSpacing(14)

        avatar = QLabel('🤖', hero_card)
        avatar.setFont(theme.qfont(theme.FONT_FAMILY, 32))
        h_hero.addWidget(avatar)

        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        p_name = QLabel('COMMANDER // PILOT-01', hero_card)
        p_name.setFont(theme.qfont(theme.FONT_FAMILY, 12, True))
        p_name.setStyleSheet('color: %s;' % theme.FG)
        v_info.addWidget(p_name)

        p_rank = QLabel('RANK: MECH SPECIALIST [LV.99] • SYSTEM: FULLY CALIBRATED', hero_card)
        p_rank.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        p_rank.setStyleSheet('color: %s;' % theme.ACCENT)
        v_info.addWidget(p_rank)
        h_hero.addLayout(v_info)
        h_hero.addStretch(1)

        root.addWidget(hero_card)

        # Stats Grid
        grid_card = QFrame(self)
        grid_card.setObjectName('hudCard')
        grid_card.setStyleSheet('QFrame#hudCard { background: #111722; border: 1px solid %s; border-radius: 8px; }' % theme.BORDER)
        grid = QGridLayout(grid_card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setSpacing(12)

        stats = [
            ('TOTAL COINS HARVESTED', '124,592,000', theme.AMBER),
            ('TOTAL EXP GENERATED', '89,420,100', theme.ACCENT),
            ('AUTO COMBAT EFFICIENCY', '99.4%', theme.GREEN),
            ('OPERATION UPTIME', '342h 18m', theme.FG),
        ]
        for idx, (t, v, c) in enumerate(stats):
            r, col = idx // 2, idx % 2
            bx = QFrame(grid_card)
            bx.setStyleSheet('background: #0B0E14; border: 1px solid %s; border-radius: 6px; padding: 10px;' % theme.BORDER)
            vb = QVBoxLayout(bx)
            vb.setSpacing(4)
            lt = QLabel(t, bx)
            lt.setFont(theme.qfont(theme.FONT_FAMILY, 7, True))
            lt.setStyleSheet('color: %s;' % theme.FG_MUTED)
            vb.addWidget(lt)
            lv = QLabel(v, bx)
            lv.setFont(theme.qfont(theme.FONT_MONO, 14, True))
            lv.setStyleSheet('color: %s;' % c)
            vb.addWidget(lv)
            grid.addWidget(bx, r, col)

        root.addWidget(grid_card, 1)
