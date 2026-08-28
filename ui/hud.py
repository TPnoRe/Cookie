"""HUD Overlay — ระบบ overlay หน้าจอ Emulator สไตล์ Mecha (PyQt6).

แยกไฟล์จาก dashboard.py เพื่อความเป็นระเบียบ:
- Corner Brackets (มุม 4 ด้าน)
- Outer Circle (วงนอก + arc segments หมุน)
- Inner Circle (วงใน breathing)
- Crosshairs (กากบาท หมุน)
- Hexagon Core (六角形 หมุน แสดงเฉพาะ offline)
- Equalizer Bars (แถบเสียง สุ่มความสูง)
"""
import math

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
)
from PyQt6.QtWidgets import QGraphicsView, QFrame

from ui import theme


class HudView(QGraphicsView):
    """จอ HUD overlay พร้อม animation — ใช้คู่กับ QGraphicsScene ของ dashboard."""

    def __init__(self, owner, scene, parent=None):
        super().__init__(scene, parent)
        self._owner = owner
        self._spin = 0.0
        self._t = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

        self.setBackgroundBrush(QColor('#080B10'))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # ── Timer ─────────────────────────────────────────────
    def _tick(self):
        qimg = getattr(self._owner, '_live_qimg', None)
        offline = qimg is None or qimg.isNull()
        if offline:
            self._spin = (self._spin + 1.5) % 360.0
        self._t += 0.05
        self.viewport().update()

    # ── Background: screenshot หรือ grid ──────────────────
    def drawBackground(self, painter, rect):
        vp = self.viewport().rect()
        painter.save()
        painter.resetTransform()
        painter.fillRect(vp, QColor('#080B10'))

        qimg = getattr(self._owner, '_live_qimg', None)
        if qimg is not None and not qimg.isNull():
            target = vp.adjusted(6, 6, -6, -6)
            scaled = qimg.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = target.x() + (target.width() - scaled.width()) // 2
            y = target.y() + (target.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        else:
            pen = QPen(QColor('#121824'), 1, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            w, h = vp.width(), vp.height()
            for gx in range(0, w, 24):
                painter.drawLine(gx, 0, gx, h)
            for gy in range(0, h, 24):
                painter.drawLine(0, gy, w, gy)

        painter.restore()

    # ── Foreground: HUD overlay + animation ────────────────
    def drawForeground(self, painter, rect):
        vp = self.viewport().rect()
        painter.save()
        painter.resetTransform()

        w, h = vp.width(), vp.height()
        cx, cy = w / 2.0, h / 2.0

        qimg = getattr(self._owner, '_live_qimg', None)
        offline = qimg is None or qimg.isNull()
        spin = self._spin if offline else 0.0
        t = self._t

        CYAN = QPen(QColor(theme.ACCENT), 1.5)
        DIM = QPen(QColor(0, 240, 255, 120), 1)

        # ── 1. Corner Brackets (นิ่ง, แสดงตลอด) ──
        m, bl = 12, 18
        painter.setPen(CYAN)
        for x1, y1, dx, dy in [
            (m, m, bl, 0), (m, m, 0, bl),
            (w - m, m, -bl, 0), (w - m, m, 0, bl),
            (m, h - m, bl, 0), (m, h - m, 0, -bl),
            (w - m, h - m, -bl, 0), (w - m, h - m, 0, -bl),
        ]:
            painter.drawLine(x1, y1, x1 + dx, y1 + dy)

        if offline:
            # ── 2. Radii ──
            R = min(w, h) * 0.20
            r_in = R * 0.45
            r_hex = r_in * 0.72

            # ── 3. Outer Circle: วงจาง + arc 4 ชิ้นหมุน ──
            orect = QRectF(cx - R, cy - R, R * 2, R * 2)
            painter.setPen(DIM)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), R, R)

            painter.setPen(CYAN)
            for base in (0, 90, 180, 270):
                painter.drawArc(orect, int((base + spin) % 360) * 16, 30 * 16)

            # ── 4. Inner Circle: breathing ──
            breath = 1.0 + 0.08 * math.sin(t)
            painter.setPen(DIM)
            painter.drawEllipse(QPointF(cx, cy), r_in * breath, r_in * breath)

            # ── 5. Crosshairs: หมุน ──
            ch = R * 0.6
            sr = math.radians(spin)

            def rot(px, py):
                dx, dy = px - cx, py - cy
                return (
                    int(cx + dx * math.cos(sr) - dy * math.sin(sr)),
                    int(cy + dx * math.sin(sr) + dy * math.cos(sr)),
                )

            painter.setPen(CYAN)
            for p1, p2 in [
                ((cx - ch, cy), (cx - 6, cy)),
                ((cx + 6, cy), (cx + ch, cy)),
                ((cx, cy - ch), (cx, cy - 6)),
                ((cx, cy + 6), (cx, cy + ch)),
            ]:
                painter.drawLine(*rot(*p1), *rot(*p2))
            painter.drawPoint(int(cx), int(cy))

            # ── 6. Hexagon Core: หมุน ──
            layers = [
                (1.00, QColor(0, 240, 255, 220), QColor(0, 240, 255, 45), 2.0),
                (0.78, QColor('#080B10'), None, 2.2),
                (0.56, QColor(theme.ACCENT), QColor(theme.ACCENT), 1.2),
            ]
            for scale, pen_c, brush_c, width in layers:
                path = QPainterPath()
                for i in range(6):
                    ang = math.radians(30 + i * 60 + spin)
                    px = cx + r_hex * scale * math.cos(ang)
                    py = cy + r_hex * scale * math.sin(ang)
                    if i == 0:
                        path.moveTo(px, py)
                    else:
                        path.lineTo(px, py)
                path.closeSubpath()
                painter.setPen(QPen(pen_c, width))
                painter.setBrush(QBrush(brush_c) if brush_c else Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(theme.AMBER)))
            painter.drawEllipse(QPointF(cx, cy), r_hex * 0.22, r_hex * 0.22)

        painter.restore()
