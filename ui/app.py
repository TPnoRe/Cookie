"""App — ตัวเชื่อมทุกส่วนของ UI เข้าด้วยกัน + ระบบสลับหน้า (PyQt6).

หน้า UI ไม่ต้องแตะ core.window โดยตรง (ยกเว้นผ่าน self.window)
"""
import datetime
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ui import theme
from ui.sidebar import Sidebar
from ui.topbar import TopBar
from ui.components import Toast
from ui.config import Config
from ui.pages.dashboard import Dashboard
from ui.pages.settings import Settings
from ui.pages.coordinates import Coordinates
from emulator.client import EmulatorClient


class _AppSignals(QObject):
    push_msg = pyqtSignal(str, str)


class App:
    """ตัวควบคุมหลักของโปรแกรม — เก็บ window system + หน้า UI ทั้งหมด."""

    def __init__(self, window):
        self.window = window
        self._running = False
        self._bot_thread = None
        self.debug_log = False
        self._on_resize = None
        self._detecting_emulator = False
        self._health_check_active = False
        self._error_dialog_open = False
        self.config = Config()
        self.emulator = EmulatorClient(
            get_settings=lambda: self.config.settings)
        self._signals = _AppSignals()
        self._signals.push_msg.connect(self._on_push_msg)
        self.pages = {}
        self._build()
        self._navigate('dashboard')
        self.update_sys_status()

        # เริ่มต้น Touch Overlay บน Main GUI Thread
        from emulator.overlay import init_overlay
        init_overlay()

        self.window.bind_resize(self._handle_resize)
        self.window.after(0, self.window.emit_resize)
        self.window.after(500, self._start_emulator_detection)

    # ── Layout ───────────────────────────────────────────
    def _build(self):
        self.main = QWidget()
        self.main.setObjectName('root')
        self.window.set_content(self.main)

        root = QHBoxLayout(self.main)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(on_navigate=self._navigate)
        root.addWidget(self.sidebar)

        self._right = QWidget()
        self._right.setObjectName('transparent')
        col = QVBoxLayout(self._right)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self.topbar = TopBar()
        col.addWidget(self.topbar)

        self.content = QStackedWidget()
        self.content.setObjectName('transparent')
        self.pages = {
            'dashboard': Dashboard(self.content, self),
            'settings': Settings(self.content, self),
            'coordinates': Coordinates(self.content, self),
        }
        for page in self.pages.values():
            self.content.addWidget(page)
        col.addWidget(self.content, 1)

        self.toast_widget = Toast(self._right)

        root.addWidget(self._right, 1)

    def _navigate(self, page):
        from ui.dropdown.dropdown import _active_popup
        if _active_popup is not None:
            _active_popup.close()
        self.content.setCurrentWidget(self.pages[page])
        self.topbar.set_page(page)
        self.sidebar.set_active(page)

    def _handle_resize(self, event):
        self.topbar.set_size(event.width, event.height)
        self.toast_widget._position()
        if self._on_resize:
            self._on_resize(event)

    def show_toast(self, level, text, duration=3000):
        self.toast_widget.show_toast(level, text, duration)

    def report_error(self, title, details, write_log=True):
        """Write and show a full crash-style error report on the GUI thread."""
        if not details.startswith('=== Crash ==='):
            details = ('=== Crash === %s\n%s\n' % (
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                details.rstrip()))

        if write_log:
            try:
                log_path = Path(__file__).resolve().parents[1] / 'crash.log'
                with log_path.open('a', encoding='utf-8') as f:
                    f.write(details)
            except OSError:
                pass

        self.dashboard_push('err', title)
        if self._error_dialog_open:
            return

        self._error_dialog_open = True
        try:
            dialog = QDialog(self.window.win)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.setMinimumSize(760, 460)

            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel('An error occurred. The full report is also saved in crash.log.'))
            report = QPlainTextEdit(dialog)
            report.setReadOnly(True)
            report.setPlainText(details)
            layout.addWidget(report, 1)

            close_button = QPushButton('Close', dialog)
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)
            dialog.exec()
        finally:
            self._error_dialog_open = False

    # ── Hook สำหรับหน้าที่ 3 ──────────────────────────────
    def on_resize(self, callback):
        """หน้า UI ใช้ลงทะเบียน event resize ได้ (เช่น วาด preview ใหม่)."""
        self._on_resize = callback

    def update_sys_status(self, status=None, color=None):
        """อัปเดตสถานะ SYS.STATUS บน Sidebar."""
        if not hasattr(self, 'sidebar'):
            return
        if status is not None:
            self.sidebar.set_status(status, color)
            return
        if self._running:
            self.sidebar.set_status('RUNNING', theme.GREEN)
        elif self.emulator.connected:
            self.sidebar.set_status('READY', theme.ACCENT)
        else:
            self.sidebar.set_status('OFFLINE', theme.FG_MUTED)

    # ── Emulator Auto-Detection & Health Check ────────────
    def _start_emulator_detection(self):
        """เริ่มค้นหา Emulator อัตโนมัติ — จะหาไปเรื่อยๆ จนกว่าจะเจอ."""
        if getattr(self, '_detecting_emulator', False):
            return
        self._detecting_emulator = True
        self._health_check_active = False
        self._detect_emulator_step()

    def _stop_emulator_detection(self):
        """หยุดระบบค้นหา Emulator เมื่อเจอและเชื่อมต่อสำเร็จแล้ว."""
        self._detecting_emulator = False

    def _detect_emulator_step(self):
        """วนค้นหา Emulator: หากยังไม่เจอจะหาต่อไปเรื่อยๆ หากเจอแล้วจะหยุดทันที."""
        if not getattr(self, '_detecting_emulator', False):
            return

        # ถ้าเชื่อมต่ออยู่แล้วและขนาดจอถูกต้อง ให้หยุดค้นหาทันที
        if self.emulator.connected and self.emulator.is_alive():
            size = self.emulator.get_size()
            if size and size[0] >= 200 and size[1] >= 200:
                self._stop_emulator_detection()
                self._start_health_check()
                return

        ok = self.emulator.connect()
        if ok:
            name = self.emulator.emulator_name
            size = self.emulator.get_size() or (0, 0)
            self.pages['dashboard'].sync_emulator_ui()
            self.update_sys_status()
            self.show_toast('ok', '%s connected' % name)
            self.dashboard_push('ok', '%s connected (%dx%d)' % (name, size[0], size[1]))
            # ตรวจพบและเชื่อมต่อเรียบร้อย -> หยุดระบบ Detection ทันที
            self._stop_emulator_detection()
            # เริ่มระบบ Health Check คอยตรวจจับกรณี Emulator ปิด
            self._start_health_check()
        else:
            # ยังไม่เจอ -> ค้นหาต่อไปเรื่อยๆ ทุก 2 วินาที
            self.window.after(2000, self._detect_emulator_step)

    def _start_health_check(self):
        """เริ่มตรวจสุขภาพหน้าต่าง Emulator ทุก 1 วินาที (เมื่อเชื่อมต่ออยู่)."""
        self._health_check_active = True
        self.window.after(1000, self._health_check_tick)

    def _health_check_tick(self):
        """ตรวจว่า Emulator ยังอยู่หรือไม่ — หากปิดไป จะเริ่มค้นหาใหม่อัตโนมัติ."""
        if not getattr(self, '_health_check_active', False) or not self.emulator.connected:
            return

        is_alive = self.emulator.is_alive()
        size = self.emulator.get_size()

        if not is_alive or not size or size[0] < 200 or size[1] < 200:
            # ตรวจพบว่า Emulator ปิดไปแล้ว
            self._health_check_active = False
            if self._running:
                self.stop_bot()
                self.dashboard_push('warn', 'Bot stopped — emulator window closed')
            self.emulator.disconnect()
            self.pages['dashboard'].sync_emulator_ui()
            self.update_sys_status()
            self.show_toast('warn', 'Emulator disconnected')
            # เริ่มค้นหาใหม่อัตโนมัติทันที
            self._start_emulator_detection()
            return

        # ทำงานปกติ วนตรวจสุขภาพต่อทุก 1 วินาที
        self.window.after(1000, self._health_check_tick)

    def connect_emulator(self):
        ok = self.emulator.connect()
        self.pages['dashboard'].sync_emulator_ui()
        self.update_sys_status()
        if ok:
            name = self.emulator.emulator_name
            size = self.emulator.get_size() or (0, 0)
            self.show_toast('ok', '%s connected' % name)
            self.dashboard_push('ok', '%s connected (%dx%d)' % (name, size[0], size[1]))
            self._stop_emulator_detection()
            self._start_health_check()
        else:
            self.show_toast('error', self.emulator.error or 'Connect failed')
            self.dashboard_push('warn', self.emulator.error or 'Connect failed')
            self._start_emulator_detection()
        return ok

    def disconnect_emulator(self):
        self._health_check_active = False
        self.emulator.disconnect()
        self.pages['dashboard'].sync_emulator_ui()
        self.update_sys_status()
        self.show_toast('warn', 'Emulator disconnected')
        # เริ่มค้นหาใหม่เรื่อยๆ
        self._start_emulator_detection()

    def get_emulator_screenshot(self):
        return self.emulator.screenshot()

    # ── Bot actions ─────────────────────────────────────
    def is_running(self):
        return self._running

    def start_bot(self, farm_mode=None):
        if self._running:
            return
        if not self.emulator.connected:
            self.show_toast('error', 'Emulator not connected')
            return
        if farm_mode is None:
            farm_mode = self.config.settings.get('farm_mode', 'farm_gold')
        self._running = True
        self._bot_thread = None
        self.update_sys_status('RUNNING', theme.GREEN)
        try:
            from game.bot import BotThread
            self._bot_thread = BotThread(self, farm_mode)
            self._bot_thread.log_message.connect(self._on_bot_log)
            self._bot_thread.stage_changed.connect(self._on_stage_changed)
            self._bot_thread.bot_finished.connect(self._on_bot_finished)
            self._bot_thread.run_completed.connect(self._on_run_completed)
            self._bot_thread.start()
        except Exception as e:
            self._running = False
            self._bot_thread = None
            self.update_sys_status('ERROR', theme.RED)
            import traceback
            self.report_error('Failed to start bot', traceback.format_exc())
            return

    def stop_bot(self):
        if not self._running:
            return
        if self._bot_thread:
            self._bot_thread.stop()
            self._bot_thread.wait(5000)
            self._bot_thread.reset()
        self._running = False
        self._bot_thread = None
        self.update_sys_status()
        self.dashboard_push('warn', 'Bot stopped — all states reset')

    def _on_bot_log(self, level, message):
        if level == 'info' and not self.debug_log:
            return
        self.dashboard_push(level, message)
        if level in ('err', 'error'):
            self.report_error('Bot error', message)

    def _on_stage_changed(self, stage):
        self.pages['dashboard'].update_stage(stage)
        if self._running:
            self.update_sys_status(stage.upper(), theme.GREEN)

    def _on_run_completed(self):
        pass

    def _on_bot_finished(self):
        self._running = False
        if self._bot_thread:
            self._bot_thread.reset()
        self._bot_thread = None
        self.update_sys_status()
        dash = self.pages.get('dashboard')
        if dash:
            dash._reset_buttons()
            dash._reset_stats()
            dash.hud_stage.setText('\u25CF  IDLE')

    def dashboard_push(self, level, message):
        if 'dashboard' in self.pages:
            self.pages['dashboard'].push_log(level, message)
        if 'logs' in self.pages:
            self.pages['logs'].push_log(level, message)

    def push_msg_threadsafe(self, level, message):
        self._signals.push_msg.emit(level, message)

    def _on_push_msg(self, level, message):
        self.dashboard_push(level, message)

    def save_settings(self, data, notify=True):
        self.config.update_settings(data)
        ok = self.config.save()
        if notify:
            if ok:
                self.show_toast('ok', 'Settings saved')
            else:
                self.show_toast('error', 'Failed to save settings')
        if self._bot_thread and self._running:
            self._bot_thread.on_settings_updated()

    def test_coordinate(self, stage, index):
        coord = self.pages.get('coordinates')
        if coord is None:
            self.dashboard_push('warn', 'Coordinates page not loaded')
            return
        points = coord._data.get(stage, [])
        if index >= len(points):
            self.dashboard_push('warn', 'No point %s #%d' % (stage, index + 1))
            return
        name, x_pct, y_pct = points[index][0], points[index][1], points[index][2]
        if not self.emulator.connected:
            self.dashboard_push('warn', 'Emulator not connected')
            return
        ok = self.emulator.tap(x_pct, y_pct)
        if ok:
            self.dashboard_push('ok', 'Tap %s #%d %s (%.1f%%, %.1f%%)' % (
                stage, index + 1, name, x_pct, y_pct))
        else:
            self.dashboard_push('warn', 'Tap failed %s #%d' % (stage, index + 1))
