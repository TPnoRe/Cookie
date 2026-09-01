"""Coordinates — หน้าจัดการพิกัดแตะ: จอ Emulator ใหญ่ + ลิสต์ + เอดิเตอร์ (PyQt6).

- โหมด Frame: แสดงเฉพาะกรอบ (จุดไม่แสดง) ลากตัวกรอบย้ายพิกัด ลากขอบ/มุมปรับ W/H
- โหมด Point: แสดงเฉพาะจุด ใช้ลากย้ายพิกัด
- คอลัมน์ขวา = เลือก stage + ลิสต์จุด (ยืด) + เอดิเตอร์ (คงที่)
"""
import io
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QGraphicsScene, QGraphicsView,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from ui import theme
from ui.config.defaults import DEFAULT_COORDINATES
from ui.components import ConfirmDialog
from ui.dropdown import Dropdown
from core.responsive import make_grid

STAGES = ['lobby', 'prep', 'gameplay', 'results']

_OVERLAY_COLORS = (theme.ACCENT_GLOW, theme.BLUE, theme.GREEN,
                   theme.YELLOW, theme.PURPLE_GLOW, theme.RED)


class _PointRow(QFrame):
    """แถวรายการพิกัดในลิสต์ — ชื่อ + พิกัด + สถานะเลือก."""

    def __init__(self, parent, index, name, x, y, w, h, selected, on_click):
        super().__init__(parent)
        self.setObjectName('pointRow')
        self.setFixedHeight(40)
        style = (
            'QFrame#pointRow { background: %s; border: 1px solid %s;'
            ' border-radius: 6px; }'
            % (theme.ACCENT_SOFT if selected else theme.BG_INPUT,
               theme.ACCENT if selected else theme.BORDER))
        self.setStyleSheet(style)
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 5, 10, 5)
        root.setSpacing(6)

        txt = QFrame(self)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        name_lbl = QLabel('%d. %s' % (index, name), txt)
        name_lbl.setFont(theme.qfont(*theme.SMALL_FONT))
        name_lbl.setStyleSheet('color: %s; background: transparent;'
                               % (theme.FG if selected else theme.FG_DIM))
        v.addWidget(name_lbl)
        coords_lbl = QLabel('X: %.0f, Y: %.0f, W: %d, H: %d' % (x, y, w, h), txt)
        coords_lbl.setFont(theme.qfont(*theme.XS_FONT))
        coords_lbl.setStyleSheet('color: %s; background: transparent;'
                                 % (theme.ACCENT_GLOW if selected
                                    else theme.FG_MUTED))
        v.addWidget(coords_lbl)
        root.addWidget(txt)
        root.addStretch(1)

        arrow = QLabel('\u203A', self)
        arrow.setStyleSheet('color: %s; background: transparent;'
                            % (theme.ACCENT_GLOW if selected
                               else theme.FG_MUTED))
        arrow.setFont(theme.qfont(theme.FONT_FAMILY, 14))
        root.addWidget(arrow)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()


class _Viewport(QGraphicsView):
    """จอ Emulator — ลากย้ายจุด, ลากขอบ/มุมปรับขนาดกรอบ."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QColor('#0D0E14'))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setRenderHints(self.renderHints()
                            | QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.TextAntialiasing)

    def drawBackground(self, painter, rect):
        qimg = getattr(self._owner, '_live_qimg', None)
        if qimg is not None and not qimg.isNull():
            painter.save()
            painter.resetTransform()
            vp = self.viewport()
            painter.fillRect(vp.rect(), QColor('#0D0E14'))
            painter.drawImage(vp.rect(), qimg)
            painter.restore()
            return
        super().drawBackground(painter, rect)

    def _scene_xy(self, event):
        pos = self.mapToScene(event.position().toPoint())
        return pos.x(), pos.y()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._owner._on_viewport_press(*self._scene_xy(event))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._owner._is_interacting():
            self._owner._on_viewport_motion(*self._scene_xy(event))
            event.accept()
            return
        self._owner._on_viewport_hover(*self._scene_xy(event))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._owner._on_viewport_release()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._owner._render_viewport()


class Coordinates(QFrame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._stage = 'lobby'
        self._selected = 0
        cfg = getattr(app, 'config', None)
        self._mode = cfg.settings.get('coord_mode', 'frame') if cfg else 'frame'
        self._drag_idx = None
        self._resize = None
        self._updating = False
        self._live_qimg = None
        self._screenshot_timer = QTimer(self)
        self._screenshot_timer.timeout.connect(self._refresh_screenshot)
        self._data = {
            s: [list(p) for p in self._load_stage(s)]
            for s in STAGES
        }
        self._build()
        if hasattr(app, 'on_resize'):
            app.on_resize(lambda ev: self._render_viewport())

    def _load_stage(self, stage):
        cfg = getattr(self.app, 'config', None)
        if cfg is not None:
            return cfg.get_coords(stage)
        return [list(p) for p in DEFAULT_COORDINATES.get(stage, [])]

    def _persist(self):
        cfg = getattr(self.app, 'config', None)
        if cfg is None:
            return
        for stage, points in self._data.items():
            cfg.set_coords(stage, points)
        cfg.save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_vision_overlay') and self._vision_overlay.isVisible():
            self._vision_overlay.setGeometry(self.rect())

    def _build(self):
        make_grid(self, columns=2, rows=1, col_weights=[6, 4])
        self._build_viewport()
        self._build_right()
        self._build_vision_overlay()

    # ── ซ้าย: จอ Emulator (ใหญ่สุด) ──────────────────────
    def _build_viewport(self):
        card = QFrame(self)
        card.setObjectName('card')
        self.layout().addWidget(card, 0, 0)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(6)

        hud = QFrame(card)
        hud.setObjectName('transparent')
        h = QHBoxLayout(hud)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(8)

        title = QLabel('\u25C8  EMULATOR VIEWPORT', hud)
        title.setFont(theme.qfont(*theme.SECTION_FONT))
        h.addWidget(title)
        h.addStretch(1)

        self.view_stage = QLabel('LOBBY', hud)
        self.view_stage.setFont(theme.qfont(*theme.XS_FONT))
        self.view_stage.setStyleSheet(
            'QLabel { background: %s; color: %s; border-radius: 4px;'
            ' padding: 2px 8px; }' % (theme.ACCENT_SOFT, theme.ACCENT_GLOW))
        h.addWidget(self.view_stage)

        self.mode_seg = QFrame(hud)
        self.mode_seg.setObjectName('transparent')
        seg_h = QHBoxLayout(self.mode_seg)
        seg_h.setContentsMargins(0, 0, 0, 0)
        seg_h.setSpacing(0)
        self._mode_buttons = {}
        self._mode_group = QButtonGroup(self.mode_seg)
        self._mode_group.setExclusive(True)
        for m in ('Frame', 'Point'):
            btn = QPushButton(m, self.mode_seg)
            btn.setProperty('btn', 'seg')
            btn.setFont(theme.qfont(theme.FONT_FAMILY, 8, True))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, val=m: self._on_mode(val))
            seg_h.addWidget(btn)
            self._mode_group.addButton(btn)
            self._mode_buttons[m.lower()] = btn
        self._style_mode()
        h.addWidget(self.mode_seg)

        self.scene = QGraphicsScene(self)
        self.view = _Viewport(self)
        self.view.setScene(self.scene)
        v.addWidget(hud)
        v.addWidget(self.view, 1)

    def _is_interacting(self):
        return self._drag_idx is not None or self._resize is not None

    def _px_radius(self, px=22):
        w = max(1, self.view.width())
        return px * 100.0 / w

    # ── วาดจอ ────────────────────────────────────────────
    def _refresh_screenshot(self):
        if not (hasattr(self.app, 'emulator')
                and self.app.emulator.connected):
            return
        img = self.app.get_emulator_screenshot()
        if img is None:
            return
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qimg = QImage.fromData(buf.getvalue())
        if qimg.isNull():
            return
        self._live_qimg = qimg
        self.view.viewport().update()

    def _render_viewport(self):
        self.scene.clear()
        self.scene.setSceneRect(0, 0, 100, 100)

        live = getattr(self, '_live_qimg', None)
        if live is None or live.isNull():
            grid = QPen(QColor('#15161F'))
            for x in range(0, 101, 10):
                self.scene.addLine(x, 0, x, 100, grid)
            for y in range(0, 101, 10):
                self.scene.addLine(0, y, 100, y, grid)

        points = self._data.get(self._stage, [])
        for i, p in enumerate(points):
            if i != self._selected:
                continue
            name, x, y, bw, bh = p[0], p[1], p[2], p[3], p[4]
            color = QColor(theme.ACCENT)
            glow = QColor(theme.ACCENT_GLOW)

            if self._mode == 'frame':
                w, h = max(2.0, bw), max(2.0, bh)
                x0, y0 = x - w / 2, y - h / 2
                self.scene.addRect(x0, y0, w, h, QPen(glow, 0.4))
                self.scene.addRect(x0, y0, w, h, QPen(color, 0.8))
                hd = 1.6
                for hx, hy in ((x0, y0), (x0 + w, y0),
                               (x0, y0 + h), (x0 + w, y0 + h)):
                    self.scene.addRect(hx - hd, hy - hd, hd * 2, hd * 2,
                                       QPen(color), QColor(color))
                idx = self.scene.addText('%d. %s' % (i + 1, name))
                idx.setDefaultTextColor(glow)
                idx.setFont(theme.qfont(theme.FONT_FAMILY, 3, True))
                idx.setPos(x0 + 0.8, y0 - 2.0)
            else:
                cross = QPen(glow, 0.3)
                self.scene.addLine(x - 2.4, y, x + 2.4, y, cross)
                self.scene.addLine(x, y - 2.4, x, y + 2.4, cross)
                self.scene.addEllipse(x - 1.0, y - 1.0, 2.0, 2.0,
                                      QPen(color), QColor(color))
                idx = self.scene.addText('%d. %s' % (i + 1, name))
                idx.setDefaultTextColor(glow)
                idx.setFont(theme.qfont(theme.FONT_FAMILY, 3, True))
                idx.setPos(x + 1.0, y - 2.2)

        vw = max(1, self.view.viewport().width())
        vh = max(1, self.view.viewport().height())
        self.view.resetTransform()
        self.view.scale(vw / 100.0, vh / 100.0)

    def _on_mode(self, value):
        self._mode = value.lower()
        cfg = getattr(self.app, 'config', None)
        if cfg:
            cfg.settings['coord_mode'] = self._mode
            cfg.save()
        self._style_mode()
        self._render_viewport()

    def _style_mode(self):
        for key, btn in self._mode_buttons.items():
            active = key == self._mode
            btn.setChecked(active)
            btn.setProperty('active', active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    # ── Interact: กด / ลาก / ปล่อย ───────────────────────
    def _on_viewport_press(self, x, y):
        self._resize = None
        points = self._data.get(self._stage, [])
        if not (0 <= self._selected < len(points)):
            return
        if self._mode == 'frame':
            rh = self._hit_resize(x, y)
            if rh is not None:
                self._resize = rh
                return
        hit = self._hit_test(x, y)
        if hit is not None:
            self._drag_idx = hit
        else:
            self._drag_idx = self._selected
        self._drag_to(x, y)

    def _on_viewport_motion(self, x, y):
        if self._resize is not None:
            self._resize_to(x, y)
            return
        if self._drag_idx is None:
            return
        self._drag_to(x, y)

    def _on_viewport_release(self):
        if self._resize is not None:
            idx, key = self._resize
            points = self._data.get(self._stage, [])
            if points and idx < len(points):
                p = points[idx]
                name, x, y, bw, bh = p[0], p[1], p[2], p[3], p[4]
                self._render_list()
                if hasattr(self.app, 'dashboard_push'):
                    self.app.dashboard_push(
                        'info', '%s resized to %dx%d' % (name, bw, bh))
            self._resize = None
            return
        if self._drag_idx is None:
            return
        points = self._data.get(self._stage, [])
        if points and self._drag_idx < len(points):
            p = points[self._drag_idx]
            name, x, y = p[0], p[1], p[2]
            self._render_list()
            if hasattr(self.app, 'dashboard_push'):
                self.app.dashboard_push(
                    'info', '%s -> %.1f%%, %.1f%%' % (name, x, y))
        self._drag_idx = None

    def _on_viewport_hover(self, x, y):
        if self._mode == 'frame' and self._hit_resize(x, y) is not None:
            self.view.setCursor(Qt.CursorShape.SizeFDiagCursor)
            return
        self.view.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._hit_test(x, y) is not None
            else Qt.CursorShape.ArrowCursor)

    def _hit_resize(self, x, y, radius_px=12):
        if self._mode != 'frame':
            return None
        radius = self._px_radius(radius_px)
        points = self._data.get(self._stage, [])
        if not (0 <= self._selected < len(points)):
            return None
        p = points[self._selected]
        name, px, py, bw, bh = p[0], p[1], p[2], p[3], p[4]
        w, h = max(2.0, bw), max(2.0, bh)
        x0, y0 = px - w / 2, py - h / 2
        x1, y1 = px + w / 2, py + h / 2
        handles = {
            'nw': (x0, y0), 'ne': (x1, y0),
            'sw': (x0, y1), 'se': (x1, y1),
            'n': ((x0 + x1) / 2, y0), 's': ((x0 + x1) / 2, y1),
            'w': (x0, (y0 + y1) / 2), 'e': (x1, (y0 + y1) / 2),
        }
        best = None
        best_d = radius
        for key, (hx, hy) in handles.items():
            d = ((x - hx) ** 2 + (y - hy) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best = (self._selected, key)
        return best

    def _hit_test(self, x, y, radius_px=22):
        radius = self._px_radius(radius_px)
        points = self._data.get(self._stage, [])
        if not (0 <= self._selected < len(points)):
            return None
        p = points[self._selected]
        name, px, py, bw, bh = p[0], p[1], p[2], p[3], p[4]
        d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if d < radius:
            return self._selected
        return None

    def _clamp_pct(self, v):
        return min(100.0, max(0.0, round(v, 1)))

    def _drag_to(self, x, y):
        points = self._data.get(self._stage, [])
        if not points or self._drag_idx is None or self._drag_idx >= len(points):
            return
        idx = self._drag_idx
        p = points[idx]
        name, px, py, bw, bh = p[0], p[1], p[2], p[3], p[4]
        points[idx] = [name, self._clamp_pct(x), self._clamp_pct(y), bw, bh]
        self._set_entry(self._entries['x'], str(points[idx][1]))
        self._set_entry(self._entries['y'], str(points[idx][2]))
        self._render_viewport()

    def _resize_to(self, x, y):
        idx, key = self._resize
        points = self._data.get(self._stage, [])
        if not points or idx >= len(points):
            return
        p = points[idx]
        name, px, py, bw, bh = p[0], p[1], p[2], p[3], p[4]
        dx = abs(x - px)
        dy = abs(y - py)
        if key in ('nw', 'ne', 'sw', 'se'):
            nw_pct = min(100.0, max(1.0, round(2 * dx, 1)))
            nh_pct = min(100.0, max(1.0, round(2 * dy, 1)))
        elif key in ('e', 'w'):
            nw_pct = min(100.0, max(1.0, round(2 * dx, 1)))
            nh_pct = bh
        else:
            nw_pct = bw
            nh_pct = min(100.0, max(1.0, round(2 * dy, 1)))
        points[idx] = [name, px, py, nw_pct, nh_pct]
        self._set_entry(self._entries['w'], str(nw_pct))
        self._set_entry(self._entries['h'], str(nh_pct))
        self._render_viewport()

    # ── ขวา: stage + ลิสต์ + เอดิเตอร์ ────────────────────
    def _build_right(self):
        panel = QFrame(self)
        panel.setObjectName('transparent')
        panel.setMinimumWidth(280)
        self.layout().addWidget(panel, 0, 1)

        right_layout = QVBoxLayout(panel)
        right_layout.setContentsMargins(4, 4, 10, 8)
        right_layout.setSpacing(0)

        title = QLabel('\u2736  COORDINATES', panel)
        title.setFont(theme.qfont(*theme.SECTION_FONT))
        title.setFixedHeight(25)
        right_layout.addWidget(title)
        right_layout.addSpacing(4)

        # stage: 2x2 grid
        seg = QFrame(panel)
        seg.setObjectName('stageSeg')
        seg.setFixedHeight(65)
        seg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._stage_buttons = {}
        self._stage_group = QButtonGroup(seg)
        self._stage_group.setExclusive(True)
        sg = QGridLayout(seg)
        sg.setContentsMargins(0, 0, 0, 0)
        sg.setSpacing(3)
        sg.setColumnStretch(0, 1)
        sg.setColumnStretch(1, 1)
        for i, s in enumerate(STAGES):
            btn = QPushButton(s.upper(), seg)
            btn.setProperty('btn', 'seg')
            btn.setFont(theme.qfont(theme.FONT_FAMILY, 10, True))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, k=s: self._on_stage(k))
            sg.addWidget(btn, i // 2, i % 2)
            self._stage_group.addButton(btn)
            self._stage_buttons[s] = btn
        right_layout.addWidget(seg)
        self._style_stage_buttons()
        right_layout.addSpacing(2)

        # list (scrollable, takes remaining space)
        self._list_container = QWidget()
        self._list_container.setObjectName('transparent')
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.scroll.setWidget(self._list_container)
        right_layout.addWidget(self.scroll)

        # count + add (fixed at bottom)
        foot = QFrame(panel)
        foot.setObjectName('transparent')
        foot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(0, 4, 0, 0)
        self.count_lbl = QLabel('0 points', foot)
        self.count_lbl.setFont(theme.qfont(*theme.XS_FONT))
        self.count_lbl.setProperty('role', 'muted')
        fh.addWidget(self.count_lbl)
        fh.addStretch(1)
        btn_add = QPushButton('+ Add', foot)
        btn_add.setProperty('btn', 'primary')
        btn_add.setFont(theme.qfont(*theme.XS_FONT))
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._on_add)
        fh.addWidget(btn_add)
        right_layout.addWidget(foot)

        right_layout.addSpacing(2)

        # editor (fixed at bottom, separate card like original)
        editor_container = QFrame(panel)
        editor_container.setObjectName('transparent')
        editor_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ev = QVBoxLayout(editor_container)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(0)
        self._build_editor(editor_container)
        right_layout.addWidget(editor_container)

        self._render_list()

    def _build_editor(self, parent):
        card = QFrame(parent)
        card.setObjectName('card')
        if parent.layout() is not None:
            parent.layout().addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 6, 12, 8)
        v.setSpacing(2)

        head = QLabel('\u270E  EDIT POINT', card)
        head.setProperty('role', 'section')
        head.setFont(theme.qfont(*theme.SECTION_FONT))
        v.addWidget(head)

        name_lbl = QLabel('Name', card)
        name_lbl.setFont(theme.qfont(*theme.XS_FONT))
        name_lbl.setProperty('role', 'muted')
        v.addWidget(name_lbl)
        self.entry_name = QLineEdit(card)
        self.entry_name.setFont(theme.qfont(*theme.SMALL_FONT))
        v.addWidget(self.entry_name)

        det_lbl = QLabel('Detection', card)
        det_lbl.setFont(theme.qfont(*theme.XS_FONT))
        det_lbl.setProperty('role', 'muted')
        v.addWidget(det_lbl)
        self.entry_detection = Dropdown(card, items=['template', 'ocr'],
                                        placeholder='Select...', max_visible=3)
        self.entry_detection.current_changed.connect(
            self._on_detection_change)
        v.addWidget(self.entry_detection)

        fields = [('X (%)', 'x'), ('Y (%)', 'y'), ('W', 'w'), ('H', 'h')]
        self._entries = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        for i, (title, key) in enumerate(fields):
            lbl = QLabel(title, card)
            lbl.setFont(theme.qfont(*theme.XS_FONT))
            lbl.setProperty('role', 'muted')
            grid.addWidget(lbl, 0, i)
            entry = QLineEdit(card)
            entry.setFont(theme.qfont(*theme.XS_FONT))
            entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(entry, 1, i)
            self._entries[key] = entry
        v.addLayout(grid)

        for entry in self._entries.values():
            entry.textChanged.connect(self._on_live_edit)
        self.entry_name.textChanged.connect(self._on_live_edit)

        row1 = QFrame(card)
        row1.setObjectName('transparent')
        r1h = QHBoxLayout(row1)
        r1h.setContentsMargins(0, 0, 0, 0)
        r1h.setSpacing(4)
        btn_save = QPushButton('\u2713  Save', row1)
        btn_save.setProperty('btn', 'success')
        btn_save.setFont(theme.qfont(*theme.XS_FONT))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)
        r1h.addWidget(btn_save)
        btn_test = QPushButton('\u25B6  Test Tap', row1)
        btn_test.setProperty('btn', 'info')
        btn_test.setFont(theme.qfont(*theme.XS_FONT))
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.clicked.connect(self._on_test)
        r1h.addWidget(btn_test)
        v.addWidget(row1)

        row2 = QFrame(card)
        row2.setObjectName('transparent')
        r2h = QHBoxLayout(row2)
        r2h.setContentsMargins(0, 0, 0, 0)
        r2h.setSpacing(4)
        btn_vision = QPushButton('\u25C8  Open Vision', row2)
        btn_vision.setProperty('btn', 'dark')
        btn_vision.setFont(theme.qfont(*theme.XS_FONT))
        btn_vision.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_vision.clicked.connect(self._on_open_vision)
        r2h.addWidget(btn_vision)
        btn_del = QPushButton('\u00D7  Delete', row2)
        btn_del.setProperty('btn', 'danger')
        btn_del.setFont(theme.qfont(*theme.XS_FONT))
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(self._on_delete)
        r2h.addWidget(btn_del)
        v.addWidget(row2)

        self._load_selected()

    def _build_vision_overlay(self):
        self._vision_roi = None
        self._vision_proc_roi = None
        self._vision_overlay = QFrame(self)
        self._vision_overlay.setObjectName('visionOverlay')
        self._vision_overlay.setStyleSheet(
            'QFrame#visionOverlay {'
            ' background: rgba(0,0,0,160);'
            ' }')
        self._vision_overlay.setVisible(False)
        self._vision_overlay.installEventFilter(self)

        card = QFrame(self._vision_overlay)
        card.setObjectName('card')
        card.setFixedSize(600, 430)
        card.setStyleSheet(
            'QFrame#card { background: %s; border: 1px solid %s;'
            ' border-radius: 10px; }' % (theme.BG_CARD, theme.BORDER))
        cv = QVBoxLayout(card)
        cv.setContentsMargins(16, 12, 16, 12)
        cv.setSpacing(6)

        self._vision_head = QLabel('', card)
        self._vision_head.setProperty('role', 'section')
        self._vision_head.setFont(theme.qfont(*theme.SECTION_FONT))
        cv.addWidget(self._vision_head)

        # ── Dual preview: CROPPED (left) + PROCESSED (right) ──
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)

        # CROPPED
        crop_col = QVBoxLayout()
        crop_col.setSpacing(3)
        lbl_crop = QLabel('\u25C8  CROPPED', card)
        lbl_crop.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        lbl_crop.setStyleSheet('color: %s;' % theme.ACCENT_GLOW)
        crop_col.addWidget(lbl_crop)
        self._vision_orig_preview = QLabel(card)
        self._vision_orig_preview.setFixedHeight(180)
        self._vision_orig_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vision_orig_preview.setStyleSheet(
            'QLabel { background: %s; border: 1px solid %s;'
            ' border-radius: 6px; color: %s; }'
            % (theme.BG_INPUT, theme.BORDER, theme.FG_MUTED))
        self._vision_orig_preview.setText('Capture → CROP')
        crop_col.addWidget(self._vision_orig_preview)
        preview_row.addLayout(crop_col, 1)

        # PROCESSED
        proc_col = QVBoxLayout()
        proc_col.setSpacing(3)
        lbl_proc = QLabel('\u25C8  PROCESSED', card)
        lbl_proc.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        lbl_proc.setStyleSheet('color: %s;' % theme.AMBER)
        proc_col.addWidget(lbl_proc)
        self._vision_proc_preview = QLabel(card)
        self._vision_proc_preview.setFixedHeight(180)
        self._vision_proc_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vision_proc_preview.setStyleSheet(
            'QLabel { background: %s; border: 1px solid %s;'
            ' border-radius: 6px; color: %s; }'
            % (theme.BG_INPUT, theme.BORDER, theme.FG_MUTED))
        self._vision_proc_preview.setText('Test → OCR')
        proc_col.addWidget(self._vision_proc_preview)
        preview_row.addLayout(proc_col, 1)

        cv.addLayout(preview_row)

        # Keep backward-compat alias
        self._vision_preview = self._vision_orig_preview

        self._vision_status = QLabel('', card)
        self._vision_status.setFont(theme.qfont(*theme.XS_FONT))
        self._vision_status.setStyleSheet('color: %s;' % theme.FG_MUTED)
        self._vision_status.setWordWrap(True)
        cv.addWidget(self._vision_status)

        cv.addStretch()

        btnrow = QHBoxLayout()
        btnrow.setSpacing(6)
        btn_cap = QPushButton('\u25B6  Capture', card)
        btn_cap.setProperty('btn', 'primary')
        btn_cap.setFont(theme.qfont(*theme.XS_FONT))
        btn_cap.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cap.clicked.connect(self._vision_capture)
        btnrow.addWidget(btn_cap)
        btn_tvis = QPushButton('\u25C8  Test', card)
        btn_tvis.setProperty('btn', 'info')
        btn_tvis.setFont(theme.qfont(*theme.XS_FONT))
        btn_tvis.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tvis.clicked.connect(self._vision_test)
        btnrow.addWidget(btn_tvis)
        btn_sorig = QPushButton('\u2714  Save', card)
        btn_sorig.setProperty('btn', 'success')
        btn_sorig.setFont(theme.qfont(*theme.XS_FONT))
        btn_sorig.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sorig.clicked.connect(self._vision_save_original)
        btnrow.addWidget(btn_sorig)
        cv.addLayout(btnrow)

        btn_close = QPushButton('\u00D7  Close', card)
        btn_close.setProperty('btn', 'danger')
        btn_close.setFont(theme.qfont(*theme.XS_FONT))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self._on_close_vision)
        cv.addWidget(btn_close)

        self._vision_confirm = QFrame(card)
        self._vision_confirm.setObjectName('visionConfirm')
        self._vision_confirm.setFixedSize(320, 160)
        self._vision_confirm.setStyleSheet(
            'QFrame#visionConfirm {'
            ' background: %s; border: 2px solid %s;'
            ' border-radius: 10px; }' % (theme.BG_CARD_HOVER, theme.ORANGE))
        self._vision_confirm.setVisible(False)
        cc = QVBoxLayout(self._vision_confirm)
        cc.setContentsMargins(14, 10, 14, 10)
        cc.setSpacing(4)

        top_row = QHBoxLayout()
        icon = QLabel('\u26A0', self._vision_confirm)
        icon.setFont(theme.qfont(theme.FONT_FAMILY, 16))
        icon.setStyleSheet('color: %s;' % theme.ORANGE)
        top_row.addWidget(icon)
        cq = QLabel('Overwrite Template?', self._vision_confirm)
        cq.setFont(theme.qfont(theme.FONT_FAMILY, 12, True))
        cq.setStyleSheet('color: %s;' % theme.FG)
        top_row.addWidget(cq)
        top_row.addStretch()
        cc.addLayout(top_row)

        self._overwrite_desc = QLabel('', self._vision_confirm)
        self._overwrite_desc.setFont(theme.qfont(theme.FONT_FAMILY, 10))
        self._overwrite_desc.setStyleSheet(
            'color: %s; background: %s; border: 1px solid %s;'
            ' border-radius: 4px; padding: 10px 12px;'
            % (theme.FG_DIM, theme.BG_INPUT, theme.BORDER))
        self._overwrite_desc.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        self._overwrite_desc.setWordWrap(True)
        self._overwrite_desc.setMinimumHeight(48)
        cc.addWidget(self._overwrite_desc)

        self._overwrite_timer_lbl = QLabel(
            'Auto-cancel in 3s', self._vision_confirm)
        self._overwrite_timer_lbl.setFont(
            theme.qfont(theme.FONT_FAMILY, 9))
        self._overwrite_timer_lbl.setStyleSheet(
            'color: %s;' % theme.FG_MUTED)
        self._overwrite_timer_lbl.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        cc.addWidget(self._overwrite_timer_lbl)

        cbtn_row = QHBoxLayout()
        cbtn_row.setSpacing(12)
        cbtn_row.addStretch()
        btn_yes = QPushButton('\u2714  Yes', self._vision_confirm)
        btn_yes.setProperty('btn', 'primary')
        btn_yes.setFont(theme.qfont(theme.FONT_FAMILY, 10, True))
        btn_yes.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_yes.clicked.connect(self._on_overwrite_yes)
        cbtn_row.addWidget(btn_yes)
        btn_no = QPushButton('\u2716  No', self._vision_confirm)
        btn_no.setProperty('btn', 'danger')
        btn_no.setFont(theme.qfont(theme.FONT_FAMILY, 10))
        btn_no.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_no.clicked.connect(self._on_overwrite_no)
        cbtn_row.addWidget(btn_no)
        cbtn_row.addStretch()
        cc.addLayout(cbtn_row)

        self._vision_confirm_timer = QTimer(self)
        self._vision_confirm_timer.setSingleShot(True)
        self._vision_confirm_timer.setInterval(3000)
        self._vision_confirm_timer.timeout.connect(
            self._on_overwrite_no)
        self._overwrite_countdown = QTimer(self)
        self._overwrite_countdown.setInterval(1000)
        self._overwrite_countdown.timeout.connect(
            self._on_overwrite_tick)
        self._overwrite_remaining = 3
        self._overwrite_path = None
        self._overwrite_name = None

        self._vision_confirm.raise_()

    def eventFilter(self, obj, event):
        if obj is self._vision_overlay and event.type() == event.Type.Resize:
            card = self._vision_overlay.findChild(QFrame, 'card')
            if card:
                ox = (self._vision_overlay.width() - card.width()) // 2
                oy = (self._vision_overlay.height() - card.height()) // 2
                card.move(ox, oy)
        return super().eventFilter(obj, event)

    # ── Logic ────────────────────────────────────────────
    def _style_stage_buttons(self):
        for key, btn in self._stage_buttons.items():
            active = key == self._stage
            btn.setChecked(active)
            btn.setProperty('active', active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _on_stage(self, value):
        self._stage = value
        self._selected = 0
        self._drag_idx = None
        self._resize = None
        self._style_stage_buttons()
        self.view_stage.setText(value.upper())
        self._render_list()
        self._load_selected()
        self._render_viewport()

    def _render_list(self):
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            if item.widget() is not None:
                item.widget().deleteLater()
        points = self._data.get(self._stage, [])
        for i, p in enumerate(points):
            name, x, y, w, h = p[0], p[1], p[2], p[3], p[4]
            row = _PointRow(
                self._list_container, i + 1, name, x, y, w, h,
                selected=(i == self._selected),
                on_click=lambda idx=i: self._select(idx))
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self.count_lbl.setText('%d points' % len(points))
        row_h = 40
        max_visible = 3
        fixed_h = max_visible * row_h + 4
        self.scroll.setFixedHeight(fixed_h)
        self.scroll.setMaximumHeight(fixed_h)

    def _select(self, idx):
        self._selected = idx
        self._render_list()
        self._load_selected()
        self._render_viewport()

    def _load_selected(self):
        points = self._data.get(self._stage, [])
        if not points:
            self.entry_name.setText('')
            for e in self._entries.values():
                e.setText('')
            return
        name, x, y, w, h = points[min(self._selected, len(points) - 1)]
        self._set_entry(self.entry_name, name)
        self._set_entry(self._entries['x'], str(x))
        self._set_entry(self._entries['y'], str(y))
        self._set_entry(self._entries['w'], str(w))
        self._set_entry(self._entries['h'], str(h))
        cfg = getattr(self.app, 'config', None)
        det = cfg.get_detection(name) if cfg else 'template'
        self.entry_detection.set_current(det)

    def _set_entry(self, entry, text):
        if entry.text() != text:
            self._updating = True
            try:
                entry.setText(text)
            finally:
                self._updating = False

    def _on_live_edit(self, text=None):
        if self._updating:
            return
        points = self._data.get(self._stage, [])
        if not points or self._selected >= len(points):
            return
        idx = min(self._selected, len(points) - 1)
        try:
            x = float(self._entries['x'].text() or '0')
            y = float(self._entries['y'].text() or '0')
            w = float(self._entries['w'].text() or '0')
            h = float(self._entries['h'].text() or '0')
        except ValueError:
            return
        points[idx] = [self.entry_name.text() or 'Point', x, y, w, h]
        self._render_list()
        self._render_viewport()

    def _on_save(self):
        points = self._data.get(self._stage, [])
        if not points or self._selected >= len(points):
            return
        try:
            x = float(self._entries['x'].text() or '0')
            y = float(self._entries['y'].text() or '0')
            w = float(self._entries['w'].text() or '0')
            h = float(self._entries['h'].text() or '0')
        except ValueError:
            if hasattr(self.app, 'show_toast'):
                self.app.show_toast('error', 'Invalid coordinate values')
            return
        idx = min(self._selected, len(points) - 1)
        points[idx] = [self.entry_name.text() or 'Point', x, y, w, h]
        self._render_list()
        self._render_viewport()
        self._persist()
        if hasattr(self.app, 'show_toast'):
            self.app.show_toast('ok', '%s saved (%.1f, %.1f) %dx%d'
                                % (points[idx][0], x, y, w, h))
        if hasattr(self.app, 'dashboard_push'):
            self.app.dashboard_push(
                'ok', '%s saved (%.1f, %.1f) %dx%d'
                % (points[idx][0], x, y, w, h))

    def _on_add(self):
        name = 'Point %d' % (len(self._data.get(self._stage, [])) + 1)
        self._data.setdefault(self._stage, []).append(
            [name, 50.0, 50.0, 60, 30])
        self._selected = len(self._data[self._stage]) - 1
        self._render_list()
        self._load_selected()
        self._render_viewport()
        self._persist()
        if hasattr(self.app, 'show_toast'):
            self.app.show_toast('ok', '%s added' % name)

    def _on_delete(self):
        points = self._data.get(self._stage, [])
        if not points or self._selected >= len(points):
            return
        name = points[self._selected][0]
        dlg = ConfirmDialog(
            self, 'Delete Point',
            'Are you sure you want to delete "%s"?' % name,
            confirm_text='Delete', level='error')
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        del points[self._selected]
        self._selected = max(0, self._selected - 1)
        self._render_list()
        self._load_selected()
        self._render_viewport()
        self._persist()
        if hasattr(self.app, 'show_toast'):
            self.app.show_toast('warn', '%s deleted' % name)

    def _on_test(self):
        if hasattr(self.app, 'test_coordinate'):
            self.app.test_coordinate(self._stage, self._selected)

    def _on_detection_change(self, text):
        points = self._data.get(self._stage, [])
        if not points or self._selected >= len(points):
            return
        name = points[self._selected][0]
        cfg = getattr(self.app, 'config', None)
        if cfg:
            cfg.set_detection(name, text)
            cfg.save()

    def _on_open_vision(self):
        points = self._data.get(self._stage, [])
        if not points or self._selected >= len(points):
            if hasattr(self.app, 'show_toast'):
                self.app.show_toast('warn', 'Select a point first')
            return
        p = points[self._selected]
        self._vision_point_name = p[0]
        self._vision_head.setText(
            '\u2736  VISION: %s' % self._vision_point_name.upper())
        self._vision_status.setText('')
        for lbl, txt in ((self._vision_orig_preview, 'Capture \u2192 CROP'),
                         (self._vision_proc_preview, 'Test \u2192 OCR')):
            lbl.setText(txt)
            lbl.setPixmap(QPixmap())
        self._vision_roi = None
        self._vision_proc_roi = None
        self._vision_overlay.setGeometry(self.rect())
        self._vision_overlay.setVisible(True)
        self._vision_overlay.raise_()

    def _on_close_vision(self):
        self._vision_overlay.setVisible(False)

    # ── Helpers for dual preview ─────────────────────────
    def _set_preview_bgr(self, label, bgr):
        """Render BGR numpy array into a QLabel preview."""
        try:
            import cv2
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg.copy())
            scaled = pixmap.scaled(
                label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
        except Exception:
            pass

    def _set_preview_gray(self, label, gray):
        """Render grayscale/binary numpy array into a QLabel preview."""
        try:
            h, w = gray.shape[:2]
            qimg = QImage(gray.data, w, h, w, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(qimg.copy())
            scaled = pixmap.scaled(
                label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
        except Exception:
            pass

    def _vision_capture(self):
        if not self.app.emulator.connected:
            self._vision_status.setText('Emulator not connected')
            return
        self._vision_status.setText('Capturing...')
        from vision.engine import VisionEngine
        engine = VisionEngine()
        screenshot = self.app.emulator.screenshot()
        if screenshot is None:
            self._vision_status.setText('Cannot take screenshot')
            return
        size = self.app.emulator.get_size()
        if not size:
            self._vision_status.setText('Cannot read viewport size')
            return
        view_w, view_h = size
        points = self._data.get(self._stage, [])
        p = points[self._selected]
        self._vision_roi = engine.extract_roi(
            screenshot, p[1], p[2], p[3], p[4], view_w, view_h)
        if self._vision_roi is None:
            self._vision_status.setText('ROI extraction failed')
            return
        h, w = self._vision_roi.shape[:2]
        self._set_preview_bgr(self._vision_orig_preview, self._vision_roi)
        # Reset PROCESSED pane until Test is pressed
        self._vision_proc_preview.setPixmap(QPixmap())
        self._vision_proc_preview.setText('Test \u2192 OCR')
        self._vision_proc_roi = None
        self._vision_status.setText('Captured: %dx%d px  |  กด Test เพื่อดูภาพ PROCESSED' % (w, h))

    def _vision_test(self):
        if self._vision_roi is None:
            self._vision_status.setText('Capture screenshot first')
            return
        self._vision_status.setText('Testing...')
        from vision.engine import VisionEngine
        engine = VisionEngine()
        screenshot = self.app.emulator.screenshot()
        if screenshot is None:
            self._vision_status.setText('Cannot take screenshot')
            return
        size = self.app.emulator.get_size()
        if not size:
            self._vision_status.setText('Cannot read viewport size')
            return
        view_w, view_h = size
        points = self._data.get(self._stage, [])
        p = points[self._selected]
        name = p[0]
        det_type = self.app.config.get_detection(name)
        result = engine.detect(
            screenshot, p[1], p[2], p[3], p[4], view_w, view_h,
            name, det_type, self._stage, save_debug=True)
        if result is None:
            self._vision_status.setText('Detection failed')
            return
        if det_type == 'template':
            safe_name = name.replace(' ', '_').replace('/', '_')
            tpl_path = '\\templates\\%s\\%s.png' % (self._stage, safe_name)
            found = result.get('found')
            status = 'FOUND' if found else 'NOT FOUND'
            conf = result.get('confidence', 0)
            ms = result.get('elapsed_ms', 0)
            line = '[Template] %s: %s %s (conf=%.3f, %dms)' % (
                name, status, tpl_path, conf, ms)
            if result.get('click_x') is not None:
                line += '\nClick: (%d, %d) px' % (
                    result['click_x'], result['click_y'])
            # Template: show fresh ROI in CROPPED, keep PROCESSED as placeholder
            dbg = result.get('debug_orig_bgr') if 'debug_orig_bgr' in result else None
            if dbg is not None:
                self._set_preview_bgr(self._vision_orig_preview, dbg)
        else:
            text = result.get('text', '')
            ms = result.get('elapsed_ms', 0)
            line = '[OCR] %s: "%s" (%dms)' % (name, text, ms)
            # OCR: show CROPPED + PROCESSED side by side
            orig_bgr = result.get('debug_orig_bgr')
            proc_gray = result.get('debug_proc_gray')
            if orig_bgr is not None:
                self._set_preview_bgr(self._vision_orig_preview, orig_bgr)
                self._vision_roi = orig_bgr
            if proc_gray is not None:
                self._set_preview_gray(self._vision_proc_preview, proc_gray)
                self._vision_proc_roi = proc_gray
            else:
                self._vision_proc_preview.setText('(no proc image)')
        self._vision_status.setText(line)
        import os
        import cv2
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        debug_dir = os.path.join(root, 'debug', self._stage)
        os.makedirs(debug_dir, exist_ok=True)
        safe_name = name.replace(' ', '_').replace('/', '_')
        debug_path = os.path.join(
            debug_dir, '%s.png' % safe_name)
        if self._vision_roi is not None:
            cv2.imwrite(debug_path, self._vision_roi)

    def _vision_save_original(self):
        if self._vision_roi is None:
            self._vision_status.setText('Capture screenshot first')
            return
        import os
        import cv2
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(root, 'vision', 'templates', self._stage)
        os.makedirs(template_dir, exist_ok=True)
        points = self._data.get(self._stage, [])
        p = points[self._selected]
        safe_name = p[0].replace(' ', '_').replace('/', '_')
        path = os.path.join(template_dir, '%s.png' % safe_name)
        if os.path.isfile(path):
            self._overwrite_path = path
            self._overwrite_name = safe_name
            self._overwrite_desc.setText(
                '"%s.png" already exists.\nSave new version?' % safe_name)
            cx = (self._vision_overlay.width() - 320) // 2
            cy = (self._vision_overlay.height() - 160) // 2
            card = self._vision_overlay.findChild(QFrame, 'card')
            if card:
                cx = (card.width() - 320) // 2
                cy = (card.height() - 160) // 2
            self._vision_confirm.move(cx, cy)
            self._vision_confirm.setVisible(True)
            self._vision_confirm.raise_()
            self._overwrite_remaining = 3
            self._overwrite_timer_lbl.setText('Auto-cancel in 3s')
            self._overwrite_countdown.start()
            self._vision_confirm_timer.start()
            return
        cv2.imwrite(path, self._vision_roi)
        self._vision_status.setText('Saved: %s.png' % safe_name)

    def _on_overwrite_tick(self):
        self._overwrite_remaining -= 1
        if self._overwrite_remaining <= 0:
            self._on_overwrite_no()
            return
        self._overwrite_timer_lbl.setText(
            'Auto-cancel in %ds' % self._overwrite_remaining)

    def _on_overwrite_yes(self):
        self._vision_confirm_timer.stop()
        self._overwrite_countdown.stop()
        self._vision_confirm.setVisible(False)
        if self._overwrite_path and self._vision_roi is not None:
            import cv2
            cv2.imwrite(self._overwrite_path, self._vision_roi)
            self._vision_status.setText(
                'Saved: %s.png' % self._overwrite_name)
        self._overwrite_path = None
        self._overwrite_name = None

    def _on_overwrite_no(self):
        self._vision_confirm_timer.stop()
        self._overwrite_countdown.stop()
        self._vision_confirm.setVisible(False)
        self._overwrite_path = None
        self._overwrite_name = None
