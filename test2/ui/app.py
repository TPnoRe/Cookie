"""App — ตัวเชื่อมทุกส่วนของ UI เข้าด้วยกัน + ระบบสลับหน้า (PyQt6).

หน้า UI ไม่ต้องแตะ core.window โดยตรง (ยกเว้นผ่าน self.window)
"""
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

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
        self.debug_log = False
        self._on_resize = None
        self.config = Config()
        self.emulator = EmulatorClient(
            get_settings=lambda: self.config.settings)
        self._signals = _AppSignals()
        self._signals.push_msg.connect(self._on_push_msg)
        self.pages = {}
        self._build()
        self._navigate('dashboard')

        # เริ่มต้น Touch Overlay บน Main GUI Thread
        from emulator.overlay import init_overlay
        init_overlay()

        self.window.bind_resize(self._handle_resize)
        self.window.after(0, self.window.emit_resize)
        self.window.after(500, self._auto_connect_emulator)

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

    # ── Hook สำหรับหน้าที่ 3 ──────────────────────────────
    def on_resize(self, callback):
        """หน้า UI ใช้ลงทะเบียน event resize ได้ (เช่น วาด preview ใหม่)."""
        self._on_resize = callback

    # ── Emulator ─────────────────────────────────────────
    def _auto_connect_emulator(self):
        """เชื่อม emulator อัตโนมัติตอนเปิดโปรแกรม — retry ทุก 5 วิ ถ้ายังไม่เจอ."""
        if self.emulator.connected:
            return
        ok = self.emulator.connect()
        self.pages['dashboard'].sync_emulator_ui()
        if ok:
            self.show_toast('ok', 'Emulator connected')
            self.dashboard_push('ok', 'Emulator connected (%dx%d)'
                                % tuple(self.emulator.get_size() or (0, 0)))
        else:
            self.window.after(5000, self._auto_connect_emulator)

    def connect_emulator(self):
        ok = self.emulator.connect()
        if ok:
            self.show_toast('ok', 'Emulator connected')
            self.dashboard_push('ok', 'Emulator connected (%dx%d)'
                                % tuple(self.emulator.get_size() or (0, 0)))
        else:
            self.show_toast('error', self.emulator.error or 'Connect failed')
            self.dashboard_push('warn', self.emulator.error or 'Connect failed')
        return ok

    def disconnect_emulator(self):
        self.emulator.disconnect()
        self.show_toast('warn', 'Emulator disconnected')
        self.dashboard_push('warn', 'Emulator disconnected')

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
        try:
            from game.bot import BotThread
            self._bot_thread = BotThread(self, farm_mode)
            self._bot_thread.log_message.connect(self._on_bot_log)
            self._bot_thread.stage_changed.connect(self._on_stage_changed)
            self._bot_thread.bot_finished.connect(self._on_bot_finished)
            self._bot_thread.start()
        except Exception as e:
            self._running = False
            self._bot_thread = None
            self.dashboard_push('err', 'Failed to start bot: %s' % str(e))
            return
        self.dashboard_push('ok', 'Bot started (%s)' % farm_mode)


    def stop_bot(self):
        if not self._running:
            return
        if self._bot_thread:
            self._bot_thread.stop()
            self._bot_thread.wait(5000)
            self._bot_thread.reset()
        self._running = False
        self._bot_thread = None
        self.dashboard_push('warn', 'Bot stopped — all states reset')

    def _on_bot_log(self, level, message):
        if level == 'info' and not self.debug_log:
            return
        self.dashboard_push(level, message)

    def _on_stage_changed(self, stage):
        self.pages['dashboard'].update_stage(stage)

    def _on_bot_finished(self):
        self._running = False
        if self._bot_thread:
            self._bot_thread.reset()
        self._bot_thread = None
        dash = self.pages.get('dashboard')
        if dash:
            dash._reset_buttons()
            dash._reset_stats()
            dash.hud_stage.setText('\u25CF  IDLE')

    def dashboard_push(self, level, message):
        self.pages['dashboard'].push_log(level, message)

    def push_msg_threadsafe(self, level, message):
        self._signals.push_msg.emit(level, message)

    def _on_push_msg(self, level, message):
        self.dashboard_push(level, message)

    def save_settings(self, data):
        self.config.update_settings(data)
        ok = self.config.save()
        if ok:
            self.show_toast('ok', 'Settings saved')
        else:
            self.show_toast('error', 'Failed to save settings')
        self.dashboard_push(
            'ok' if ok else 'warn',
            'Settings saved%s' % ('' if ok else ' (write failed)'))
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
