"""Dashboard — หน้าควบคุมหลัก: สถิติ, ภาพจำลองหน้าจอ, ควบคุมบอท, บันทึกกิจกรรม (PyQt6)."""
import io
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsEllipseItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ui import theme
from core.responsive import make_grid


class _View(QGraphicsView):
    """จอแสดงผล — วาดภาพ live emulator เต็มกรอบเมื่อมีภาพ."""

    def __init__(self, owner, scene):
        super().__init__(scene)
        self._owner = owner
        self.setBackgroundBrush(QColor('#0D0E14'))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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


class StatCard(QFrame):
    """การ์ดสถิติขนาดกะทัดรัด — ไอคอน + ค่า + ป้ายชื่อ."""

    def __init__(self, parent, icon, title, value='--', color=theme.ACCENT):
        super().__init__(parent)
        self.setObjectName('card')
        self._color = color
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 8, 8)
        root.setSpacing(6)

        icon_lbl = QLabel(icon, self)
        icon_lbl.setFont(theme.qfont(theme.FONT_FAMILY, 14))
        icon_lbl.setStyleSheet('color: %s;' % color)
        root.addWidget(icon_lbl)

        txt = QFrame(self)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.value_lbl = QLabel(value, txt)
        self.value_lbl.setFont(theme.qfont(*theme.STAT_NUM_FONT))
        self.value_lbl.setStyleSheet('color: %s;' % color)
        v.addWidget(self.value_lbl)
        self.title_lbl = QLabel(title, txt)
        self.title_lbl.setFont(theme.qfont(*theme.STAT_LABEL_FONT))
        self.title_lbl.setProperty('role', 'muted')
        v.addWidget(self.title_lbl)
        root.addWidget(txt)
        root.addStretch(1)

    def set(self, value):
        self.value_lbl.setText(value)

    def set_color(self, color):
        self.value_lbl.setStyleSheet('color: %s;' % color)


class Dashboard(QFrame):
    """หน้า Dashboard — ปรับขนาดตามหน้าต่างอัตโนมัติ (layout stretch)."""

    MAX_LOG = 200

    LOG_COLORS = {
        'info': theme.FG_MUTED,
        'ok': theme.GREEN,
        'warn': theme.ORANGE,
        'err': theme.RED,
    }

    def __init__(self, parent, app):
        super().__init__(parent)
        self.setObjectName('transparent')
        self.app = app
        self._log_entries = []
        self._session_start = None
        self._runs = 0
        self._live_qimg = None
        self._screenshot_timer = QTimer(self)
        self._screenshot_timer.timeout.connect(self._refresh_screenshot)
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self.refresh)
        self._build()

    # ── Layout ───────────────────────────────────────────
    def _build(self):
        make_grid(self, columns=2, rows=3, col_weights=[7, 4],
                  row_weights=[0, 1, 0])
        self._build_stats()
        self._build_viewport_log()
        self._build_controls()

    def _build_stats(self):
        strip = QFrame(self)
        strip.setObjectName('transparent')
        self.layout().addWidget(strip, 0, 0, 1, 2)
        h = QHBoxLayout(strip)
        h.setContentsMargins(10, 10, 10, 6)
        h.setSpacing(4)

        self.stat_emulator = StatCard(
            strip, '\u25C8', 'EMULATOR', 'Offline', theme.FG_MUTED)
        self.stat_bot = StatCard(
            strip, '\u25B6', 'BOT', 'Stopped', theme.FG_MUTED)
        self.stat_runs = StatCard(
            strip, '\u21BB', 'RUNS', '0', theme.GREEN)
        self.stat_session = StatCard(
            strip, '\u23F1', 'SESSION', '00:00:00', theme.ACCENT)
        for c in (self.stat_emulator, self.stat_bot, self.stat_runs,
                  self.stat_session):
            h.addWidget(c, 1)

    def _build_viewport_log(self):
        # ซ้าย: ภาพจำลองหน้าจอ Emulator
        view_card = QFrame(self)
        view_card.setObjectName('card')
        self.layout().addWidget(view_card, 1, 0)
        v = QVBoxLayout(view_card)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(6)

        hud = QFrame(view_card)
        hud.setObjectName('transparent')
        h = QHBoxLayout(hud)
        h.setContentsMargins(4, 0, 4, 0)
        self.hud_res = QLabel('1280 x 720', hud)
        self.hud_res.setFont(theme.qfont(*theme.XS_FONT))
        self.hud_res.setStyleSheet(
            'QLabel { background: %s; color: %s; border-radius: 4px;'
            ' padding: 2px 6px; }' % (theme.ACCENT_SOFT, theme.ACCENT_GLOW))
        h.addWidget(self.hud_res)
        h.addStretch(1)
        self.hud_stage = QLabel('\u25CF  IDLE', hud)
        self.hud_stage.setFont(theme.qfont(*theme.XS_FONT))
        self.hud_stage.setProperty('role', 'muted')
        h.addWidget(self.hud_stage)
        v.addWidget(hud)

        self.scene = QGraphicsScene(self)
        self.view = _View(self, self.scene)
        self._draw_placeholder()
        v.addWidget(self.view, 1)

        # ขวา: บันทึกกิจกรรม
        log_card = QFrame(self)
        log_card.setObjectName('card')
        self.layout().addWidget(log_card, 1, 1)
        v = QVBoxLayout(log_card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        head = QFrame(log_card)
        head.setObjectName('transparent')
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        title = QLabel('\u2630  ACTIVITY LOG', head)
        title.setFont(theme.qfont(*theme.SECTION_FONT))
        h.addWidget(title)
        h.addStretch(1)
        btn_clear = QPushButton('Clear', head)
        btn_clear.setProperty('btn', 'ghost')
        btn_clear.setFont(theme.qfont(*theme.XS_FONT))
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_log)
        h.addWidget(btn_clear)
        v.addWidget(head)

        filt = QFrame(log_card)
        filt.setObjectName('transparent')
        h = QHBoxLayout(filt)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(3)
        self._filter_buttons = {}
        self._active_filter = 'ALL'
        for level in ('ALL', 'INFO', 'OK', 'WARN', 'ERR'):
            btn = QPushButton(level, filt)
            btn.setProperty('btn', 'filter')
            btn.setFont(theme.qfont(*theme.XS_FONT))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, l=level: self._set_filter(l))
            h.addWidget(btn)
            self._filter_buttons[level] = btn
        h.addStretch(1)
        v.addWidget(filt)
        self._style_filters()

        self.log_box = QPlainTextEdit(log_card)
        self.log_box.setReadOnly(True)
        self.log_box.setFont(theme.qfont(*theme.SMALL_FONT))
        self.log_box.setMaximumBlockCount(self.MAX_LOG)
        v.addWidget(self.log_box, 1)

    def _build_controls(self):
        bar = QFrame(self)
        bar.setObjectName('card')
        self.layout().addWidget(bar, 2, 0, 1, 2)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(8)

        self.btn_start = QPushButton('\u25B6  START', bar)
        self.btn_start.setProperty('btn', 'success')
        self.btn_start.setFont(theme.qfont(*theme.BTN_FONT))
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_start.setEnabled(False)
        h.addWidget(self.btn_start)

        self.btn_stop = QPushButton('\u25A0  STOP', bar)
        self.btn_stop.setProperty('btn', 'danger')
        self.btn_stop.setFont(theme.qfont(*theme.BTN_FONT))
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        h.addWidget(self.btn_stop)

        h.addStretch(1)

        self.btn_debug = QPushButton('DEBUG OFF', bar)
        self.btn_debug.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_debug.setFont(theme.qfont(*theme.SMALL_FONT))
        self.btn_debug.clicked.connect(self._toggle_debug)
        self._style_debug_btn()
        h.addWidget(self.btn_debug)

    # ── Placeholder viewport ─────────────────────────────
    def _draw_placeholder(self):
        self._live_qimg = None
        self.scene.clear()
        w, h = 640, 400
        self.scene.setSceneRect(0, 0, w, h)
        grid_pen = QPen(QColor('#15161F'))
        for x in range(0, w, 32):
            self.scene.addLine(x, 0, x, h, grid_pen)
        for y in range(0, h, 32):
            self.scene.addLine(0, y, w, y, grid_pen)

        cx, cy = w // 2, h // 2
        r = min(w, h) // 6
        pen = QPen(QColor('#2E3140'), 6)
        self.scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r, pen)
        accent = QPen(QColor(theme.ACCENT), 6)
        arc = QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r)
        arc.setPen(accent)
        arc.setStartAngle(30 * 16)
        arc.setSpanAngle(150 * 16)
        self.scene.addItem(arc)
        t1 = self.scene.addText('EMULATOR OFFLINE',
                           theme.qfont(theme.FONT_FAMILY, 10, True))
        t1.setPos(cx - t1.boundingRect().width() / 2, cy + r + 16)
        t2 = self.scene.addText('Connect emulator to see live screen',
                           theme.qfont(*theme.XS_FONT))
        t2.setPos(cx - t2.boundingRect().width() / 2, cy + r + 36)
        self.view.fitInView(self.scene.sceneRect(),
                            Qt.AspectRatioMode.KeepAspectRatio)
        self.view.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, '_live_qimg', None) is None:
            self.view.fitInView(self.scene.sceneRect(),
                                Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.view.viewport().update()

    # ── Log ──────────────────────────────────────────────
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
        bot = getattr(self.app, '_bot_thread', None)
        if bot is not None:
            self._runs = bot._runs
            self.stat_runs.set(str(self._runs))
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
        for level, ts, msg in filtered[-80:]:
            ts_fmt = QTextCharFormat()
            ts_fmt.setForeground(QColor(theme.FG_MUTED))
            msg_fmt = QTextCharFormat()
            msg_fmt.setForeground(
                QColor(self.LOG_COLORS.get(level, theme.FG)))
            cursor = self.log_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_box.setTextCursor(cursor)
            self.log_box.setCurrentCharFormat(ts_fmt)
            self.log_box.insertPlainText('%s  ' % ts)
            self.log_box.setCurrentCharFormat(msg_fmt)
            self.log_box.insertPlainText('%s\n' % msg)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _is_match(self, level):
        if self._active_filter == 'ALL':
            return True
        return level == self._active_filter.lower()

    def refresh(self):
        running = self.app.is_running() if hasattr(self.app, 'is_running') else False
        if running:
            self.stat_bot.set('Running')
            self.stat_bot.set_color(theme.GREEN)
            if not self._session_start:
                self._session_start = time.time()
        else:
            self.stat_bot.set('Stopped')
            self.stat_bot.set_color(theme.FG_MUTED)
            self._session_start = None

        bot_thread = getattr(self.app, '_bot_thread', None)
        if bot_thread is not None:
            current_stage = bot_thread.state.value
            if current_stage and current_stage != 'idle':
                self.hud_stage.setText('\u25CF  %s' % current_stage.upper())
            else:
                self.hud_stage.setText('\u25CF  %s' % ('ONLINE' if running else 'IDLE'))

        if self._session_start:
            s = int(time.time() - self._session_start)
            self.stat_session.set('%02d:%02d:%02d' % (s // 3600,
                                                       (s % 3600) // 60, s % 60))

    def update_stage(self, stage):
        """Update the HUD stage display from bot thread."""
        self.hud_stage.setText('\u25CF  %s' % stage.upper())

    # ── Actions ──────────────────────────────────────────
    def sync_emulator_ui(self):
        """อัปเดต UI ทั้งหมดตามสถานะ emulator ปัจจุบัน (ใช้กับ auto-connect)."""
        coord = self.app.pages.get('coordinates')
        connected = self.app.emulator.connected
        if connected:
            self.btn_start.setEnabled(True)
            size = self.app.emulator.get_size()
            if size:
                self.hud_res.setText('%d x %d' % (size[0], size[1]))
            self.hud_stage.setText('\u25CF  ONLINE')
            self.stat_emulator.set('Online')
            self.stat_emulator.set_color(theme.GREEN)
            self._screenshot_timer.start(500)
            self._refresh_screenshot()
            if coord:
                coord._screenshot_timer.start(500)
                coord._refresh_screenshot()
        else:
            self._screenshot_timer.stop()
            if coord:
                coord._screenshot_timer.stop()
                coord._live_qimg = None
                coord._render_viewport()
            self.btn_start.setEnabled(False)
            self.stat_emulator.set('Offline')
            self.stat_emulator.set_color(theme.FG_MUTED)
            self.hud_res.setText('1280 x 720')
            self.hud_stage.setText('\u25CF  IDLE')
            self._draw_placeholder()

    def _refresh_screenshot(self):
        if not self.app.emulator.connected:
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
        self.scene.clear()
        self.view.viewport().update()

    def _on_start(self):
        if hasattr(self.app, 'start_bot'):
            farm_mode = self.app.config.settings.get('farm_mode', 'farm_gold')
            self.app.start_bot(farm_mode)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._session_timer.start(1000)
        self.refresh()

    def _on_stop(self):
        if hasattr(self.app, 'stop_bot'):
            self.app.stop_bot()
        self._session_timer.stop()
        self._reset_buttons()
        self._reset_stats()
        self.hud_stage.setText('\u25CF  IDLE')
        self.refresh()

    def _reset_buttons(self):
        self.btn_start.setEnabled(self.app.emulator.connected)
        self.btn_stop.setEnabled(False)

    def _reset_stats(self):
        self._session_start = None
        self._session_timer.stop()
        self.stat_session.set('00:00:00')
        self.stat_bot.set('Stopped')
        self.stat_bot.set_color(theme.FG_MUTED)
        bot = getattr(self.app, '_bot_thread', None)
        if bot is not None:
            bot._runs = 0                        # reset counter
            self._runs = 0
            self.stat_runs.set('0')                  # แสดง 0

    def _toggle_debug(self):
        self.app.debug_log = not self.app.debug_log
        self._style_debug_btn()
        level = 'ok' if self.app.debug_log else 'warn'
        self.push_log(level, 'Debug log %s' %
                      ('ON (show info)' if self.app.debug_log else 'OFF (hide info)'))

    def _style_debug_btn(self):
        on = bool(self.app.debug_log)
        self.btn_debug.setText('DEBUG ON' if on else 'DEBUG OFF')
        self.btn_debug.setProperty('active', on)
        self.btn_debug.style().unpolish(self.btn_debug)
        self.btn_debug.style().polish(self.btn_debug)
        self.btn_debug.update()



