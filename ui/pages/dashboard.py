"""Dashboard — หน้าควบคุมหลัก สไตล์ Robotic Mech HUD (PyQt6).

โครงสร้างเดิม 100%:
- แถบบน: การ์ดสถิติ 4 ช่อง (EMULATOR, BOT, RUNS, SESSION) แบบตัดมุมเฉียง
- ซ้าย: จอ Live Android Emulator HUD พร้อมเรดาร์เล็งเป้าและข้อมูล Telemetry
- ขวา: บันทึกกิจกรรม Activity Log แบบเทอร์มินัลพร้อมปุ่มฟิลเตอร์
- ล่าง: แถบควบคุม START, STOP, DEBUG สไตล์ปุ่มค็อกพิทจักรกล
"""
import io
import time
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QColor, QImage, QPainter, QPen, QPixmap, QTextCharFormat, QTextCursor, QFont,
)
from PyQt6.QtWidgets import (
    QFrame, QGraphicsScene, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logo.png')

from ui import theme
from ui.hud import HudView
from ui.components import MechPanel, MechButton
from core.responsive import make_grid



class StatCard(MechPanel):
    """การ์ดสถิติขนาดกะทัดรัด สไตล์ตัดมุมเฉียง (Chamfered Stat Card)."""

    def __init__(self, parent, icon, title, value='--', color=theme.ACCENT):
        super().__init__(parent, chamfer=8, style='diagonal', bg_color='#111722', border_color=theme.BORDER)
        self._color = color
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 10, 8)
        root.setSpacing(8)

        icon_lbl = QLabel(icon, self)
        icon_lbl.setFont(theme.qfont('Segoe UI Symbol', 18, True))
        icon_lbl.setStyleSheet('color: %s;' % color)
        root.addWidget(icon_lbl)

        txt = QFrame(self)
        txt.setObjectName('transparent')
        v = QVBoxLayout(txt)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        self.value_lbl = QLabel(value, txt)
        self.value_lbl.setFont(theme.qfont(*theme.STAT_NUM_FONT))
        self.value_lbl.setStyleSheet('color: %s;' % color)
        v.addWidget(self.value_lbl)
        self.title_lbl = QLabel(title, txt)
        self.title_lbl.setFont(theme.qfont(theme.FONT_MONO, 7, True))
        self.title_lbl.setStyleSheet('color: %s;' % theme.FG_MUTED)
        v.addWidget(self.title_lbl)
        root.addWidget(txt)
        root.addStretch(1)

    def set(self, value):
        self.value_lbl.setText(value)

    def set_color(self, color):
        self.value_lbl.setStyleSheet('color: %s;' % color)


class Dashboard(QFrame):
    """หน้า Dashboard — โครงสร้างเดิม 100% พร้อม UI สไตล์ Robotic Mech HUD."""

    MAX_LOG = 200

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
        h.setSpacing(8)

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
        # ซ้าย: ภาพจำลองหน้าจอ Emulator (Cockpit Chamfered Frame)
        view_card = MechPanel(self, chamfer=12, style='cockpit', bg_color='#0E131D', border_color=theme.BORDER, glow=True)
        self.layout().addWidget(view_card, 1, 0)
        v = QVBoxLayout(view_card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        hud = QFrame(view_card)
        hud.setObjectName('transparent')
        h = QHBoxLayout(hud)
        h.setContentsMargins(4, 0, 4, 0)
        self.hud_res = QLabel('0 x 0', hud)
        self.hud_res.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        self.hud_res.setStyleSheet(
            'QLabel { background: %s; color: %s; border-radius: 4px;'
            ' padding: 2px 6px; }' % (theme.ACCENT_SOFT, theme.ACCENT_GLOW))
        h.addWidget(self.hud_res)
        h.addStretch(1)
        self.hud_stage = QLabel('●  IDLE', hud)
        self.hud_stage.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        self.hud_stage.setStyleSheet('color: %s;' % theme.FG_MUTED)
        h.addWidget(self.hud_stage)
        v.addWidget(hud)

        self.scene = QGraphicsScene(self)
        self.view = HudView(self, self.scene)
        self._draw_placeholder()
        v.addWidget(self.view, 1)

        # ขวา: บันทึกกิจกรรม Activity Log (Chamfered MechPanel)
        log_card = MechPanel(self, chamfer=10, style='diagonal', bg_color='#111722', border_color=theme.BORDER)
        self.layout().addWidget(log_card, 1, 1)
        v = QVBoxLayout(log_card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        head = QFrame(log_card)
        head.setObjectName('transparent')
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        title = QLabel('// ACTIVITY LOG', head)
        title.setFont(theme.qfont(theme.FONT_MONO, 9, True))
        title.setStyleSheet('color: %s;' % theme.ACCENT)
        h.addWidget(title)
        h.addStretch(1)
        btn_clear = QPushButton('Clear', head)
        btn_clear.setProperty('btn', 'ghost')
        btn_clear.setFont(theme.qfont(theme.FONT_MONO, 8))
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
            btn.setFont(theme.qfont(theme.FONT_MONO, 7, True))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, l=level: self._set_filter(l))
            h.addWidget(btn)
            self._filter_buttons[level] = btn
        h.addStretch(1)
        v.addWidget(filt)
        self._style_filters()

        self.log_box = QPlainTextEdit(log_card)
        self.log_box.setReadOnly(True)
        self.log_box.setFont(theme.qfont(theme.FONT_MONO, 8))
        self.log_box.setMaximumBlockCount(self.MAX_LOG)
        self.log_box.setStyleSheet(
            'QPlainTextEdit { background: #0A0D14; border: 1px solid %s; border-radius: 4px; padding: 6px; }'
            % theme.BORDER
        )
        v.addWidget(self.log_box, 1)

    def _build_controls(self):
        bar = MechPanel(self, chamfer=8, style='diagonal', bg_color='#111722', border_color=theme.BORDER)
        self.layout().addWidget(bar, 2, 0, 1, 2)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        # Single Smart Toggle Button (START / STOP)
        self.btn_toggle = MechButton('▶  START', bar, chamfer=8, btn_type='engage')
        self.btn_toggle.setFont(theme.qfont(theme.FONT_FAMILY, 9, True))
        self.btn_toggle.setFixedHeight(34)
        self.btn_toggle.setMinimumWidth(120)
        self.btn_toggle.clicked.connect(self._on_toggle_bot)
        self.btn_toggle.setEnabled(False)
        h.addWidget(self.btn_toggle)

        # Backwards compatibility handles
        self.btn_start = self.btn_toggle
        self.btn_stop = self.btn_toggle

        h.addStretch(1)

        self.btn_debug = MechButton('DEBUG OFF', bar, chamfer=8, btn_type='dark')
        self.btn_debug.setFont(theme.qfont(theme.FONT_MONO, 8, True))
        self.btn_debug.setFixedHeight(32)
        self.btn_debug.clicked.connect(self._toggle_debug)
        self._style_debug_btn()
        h.addWidget(self.btn_debug)

    # ── Placeholder viewport ─────────────────────────────
    def _draw_placeholder(self):
        self._live_qimg = None
        self.scene.clear()
        w, h = 640, 400
        self.scene.setSceneRect(0, 0, w, h)
        grid_pen = QPen(QColor('#121824'))
        for x in range(0, w, 32):
            self.scene.addLine(x, 0, x, h, grid_pen)
        for y in range(0, h, 32):
            self.scene.addLine(0, y, w, y, grid_pen)

        cx, cy = w // 2, h // 2
        t1 = self.scene.addText('EMULATOR OFFLINE',
                           theme.qfont(theme.FONT_FAMILY, 14, True))
        t1.setDefaultTextColor(QColor(theme.FG_MUTED))
        t1.setPos(cx - t1.boundingRect().width() / 2, h - 70)
        t2 = self.scene.addText('Connect emulator to see live screen',
                           theme.qfont(theme.FONT_FAMILY, 10))
        t2.setDefaultTextColor(QColor(theme.FG_MUTED))
        t2.setPos(cx - t2.boundingRect().width() / 2, h - 45)
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
            ts_fmt.setForeground(QColor(theme.ACCENT))
            msg_fmt = QTextCharFormat()
            msg_fmt.setForeground(
                QColor(self.LOG_COLORS.get(level, theme.FG)))
            cursor = self.log_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_box.setTextCursor(cursor)
            self.log_box.setCurrentCharFormat(ts_fmt)
            self.log_box.insertPlainText('[%s]  ' % ts)
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
                self.hud_stage.setText('●  %s' % current_stage.upper())
            else:
                self.hud_stage.setText('●  %s' % ('ONLINE' if running else 'IDLE'))

        if self._session_start:
            s = int(time.time() - self._session_start)
            self.stat_session.set('%02d:%02d:%02d' % (s // 3600,
                                                       (s % 3600) // 60, s % 60))

    def update_stage(self, stage):
        """Update the HUD stage display from bot thread."""
        self.hud_stage.setText('●  %s' % stage.upper())

    # ── Actions ──────────────────────────────────────────
    def sync_emulator_ui(self):
        """อัปเดต UI ทั้งหมดตามสถานะ emulator ปัจจุบัน (ใช้กับ auto-connect)."""
        coord = self.app.pages.get('coordinates')
        connected = self.app.emulator.connected
        running = self.app.is_running() if hasattr(self.app, 'is_running') else False
        if connected:
            if not running:
                self.btn_toggle.setEnabled(True)
            size = self.app.emulator.get_size()
            if size:
                self.hud_res.setText('%d x %d' % (size[0], size[1]))
            self.hud_stage.setText('●  ONLINE' if not running else '●  RUNNING')
            self.hud_stage.setStyleSheet('color: %s;' % theme.GREEN)
            emu_name = getattr(self.app.emulator, 'emulator_name', 'Online')
            self.stat_emulator.set(emu_name if emu_name != 'Emulator' else 'Online')
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
            if not running:
                self.btn_toggle.setEnabled(False)
            self.stat_emulator.set('Offline')
            self.stat_emulator.set_color(theme.FG_MUTED)
            self.hud_res.setText('0 x 0')
            self.hud_stage.setText('●  OFFLINE')
            self.hud_stage.setStyleSheet('color: %s;' % theme.FG_MUTED)
            self._draw_placeholder()

    def _refresh_screenshot(self):
        if not self.app.emulator.connected:
            self._screenshot_timer.stop()
            self.sync_emulator_ui()
            self.app._start_emulator_detection()
            return
        size = self.app.emulator.get_size()
        if not size or size[0] < 200 or size[1] < 200:
            if self.app.is_running():
                self.app.stop_bot()
                self.app.dashboard_push('warn', 'Bot stopped — emulator lost')
            self.app.emulator.disconnect()
            self.sync_emulator_ui()
            self.app.update_sys_status()
            self.app._start_emulator_detection()
            return
        res_str = '%d x %d' % (size[0], size[1])
        if self.hud_res.text() != res_str:
            self.hud_res.setText(res_str)

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

    def _on_toggle_bot(self):
        running = self.app.is_running() if hasattr(self.app, 'is_running') else False
        if not running:
            self._on_start()
        else:
            self._on_stop()

    def _on_start(self):
        settings_page = self.app.pages.get('settings')
        if settings_page and hasattr(settings_page, '_on_save'):
            settings_page._on_save(notify=False)
        if hasattr(self.app, 'start_bot'):
            farm_mode = self.app.config.settings.get('farm_mode', 'farm_gold')
            self.app.start_bot(farm_mode)
        self.btn_toggle.setText('■  STOP')
        self.btn_toggle.set_btn_type('engage-running')
        self.btn_toggle.setEnabled(True)
        self._session_timer.start(1000)
        self.refresh()

    def _on_stop(self):
        if hasattr(self.app, 'stop_bot'):
            self.app.stop_bot()
        self._session_timer.stop()
        self._reset_buttons()
        self._reset_stats()
        self.hud_stage.setText('●  IDLE')
        self.refresh()

    def _reset_buttons(self):
        connected = bool(self.app.emulator.connected)
        self.btn_toggle.setText('▶  START')
        self.btn_toggle.set_btn_type('engage')
        self.btn_toggle.setEnabled(connected)

    def _reset_stats(self):
        self._session_start = None
        self._session_timer.stop()
        self.stat_session.set('00:00:00')
        self.stat_bot.set('Stopped')
        self.stat_bot.set_color(theme.FG_MUTED)
        bot = getattr(self.app, '_bot_thread', None)
        if bot is not None:
            bot._runs = 0
            self._runs = 0
            self.stat_runs.set('0')

    def _toggle_debug(self):
        self.app.debug_log = not self.app.debug_log
        self._style_debug_btn()
        level = 'ok' if self.app.debug_log else 'warn'
        self.push_log(level, 'Debug log %s' %
                      ('ON (show info)' if self.app.debug_log else 'OFF (hide info)'))

    def _style_debug_btn(self):
        on = bool(self.app.debug_log)
        self.btn_debug.setText('DEBUG ON' if on else 'DEBUG OFF')
        self.btn_debug.set_btn_type('amber' if on else 'dark')




