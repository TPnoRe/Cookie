"""Window System — ระบบหน้าต่างโปรแกรมทั้งหมด (PyQt6).

รับผิดชอบ:
- สร้างหน้าต่างหลัก (QMainWindow ขนาดคงที่ 800x600 ไม่สามารถย่อ/ขยายได้)
- เปิด DPI scaling ตามสัดส่วนหน้าจอบน Windows
- จัดตำแหน่งหน้าต่างกลางจอ
- คุม layout ให้ทุกชิ้นส่วนยืด/หดตามพื้นที่ได้เอง
- แจ้ง event เมื่อหน้าต่างถูก resize / ย่อ-ขยาย
- จัดการการปิดโปรแกรม (close handler)

หน้าจออื่น ๆ ไม่ต้องแตะ geometry/wm โดยตรง ให้ผ่านระบบนี้เสมอ
"""
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget


def enable_dpi_awareness():
    """ตั้งค่า rounding policy ของ DPI scaling (ต้องเรียกก่อนสร้าง QApplication)."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


class ResizeEvent:
    """ตัวแทน 1 การ resize — ข้อมูลที่ส่งให้ listener."""

    def __init__(self, width, height, is_maximized, is_minimized):
        self.width = width
        self.height = height
        self.is_maximized = is_maximized
        self.is_minimized = is_minimized


class _MainWindow(QMainWindow):
    """QMainWindow ลูก — ดัก resize/close แล้วส่งต่อให้ AppWindow."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._force_close = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._owner._emit_resize()

    def closeEvent(self, event):
        if self._force_close:
            event.accept()
            return
        event.ignore()
        self._owner.request_close()


class AppWindow:
    """หน้าต่างหลักของโปรแกรม — API เดียวที่ UI ใช้ทำงานกับหน้าต่าง."""

    DEFAULT_WIDTH = 900
    DEFAULT_HEIGHT = 600

    def __init__(
        self,
        title='Cookie Run Classic Bot',
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
    ):
        enable_dpi_awareness()

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle('Fusion')
        self.app.setApplicationName(title)

        from ui import theme
        self.app.setStyleSheet(theme.app_style())

        self.title = title
        self.width = width
        self.height = height
        self._resize_listeners = []
        self._close_handlers = []

        self.win = _MainWindow(self)
        self.win.setWindowTitle(title)
        self.win.setFixedSize(width, height)
        self._center_window()

        # content area ที่ UI ใช้แทน geometry โดยตรง
        self._central = QWidget()
        self._central_layout = QVBoxLayout(self._central)
        self._central_layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.setSpacing(0)
        self.win.setCentralWidget(self._central)

    # ── Geometry ─────────────────────────────────────────
    def _center_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.win.width(), self.win.height()
        x = max(0, (screen.width() - w) // 2)
        y = max(0, (screen.height() - h) // 2)
        self.win.move(x, y)

    def get_size(self):
        return self.win.width(), self.win.height()

    def set_title(self, text):
        self.title = text
        self.win.setWindowTitle(text)

    # ── Content ──────────────────────────────────────────
    def set_content(self, widget):
        """วาง widget หลักลงในหน้าต่าง."""
        self._central_layout.addWidget(widget)

    def clear_content(self):
        """ลบ widget ทั้งหมดออกจาก central layout."""
        while self._central_layout.count():
            item = self._central_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    # ── Resize events ────────────────────────────────────
    def _emit_resize(self):
        ev = ResizeEvent(
            width=self.win.width(),
            height=self.win.height(),
            is_maximized=self.win.isMaximized(),
            is_minimized=self.win.isMinimized(),
        )
        for cb in list(self._resize_listeners):
            try:
                cb(ev)
            except Exception:
                pass

    def bind_resize(self, callback):
        """สมัคร listener รับ event resize — callback(ResizeEvent)."""
        self._resize_listeners.append(callback)

    def unbind_resize(self, callback):
        if callback in self._resize_listeners:
            self._resize_listeners.remove(callback)

    def emit_resize(self):
        """แจ้ง resize ครั้งแรกหลัง UI สร้างเสร็จ (ให้ topbar ขึ้นขนาดทันที)."""
        self.win.activateWindow()
        self._emit_resize()

    # ── Close ────────────────────────────────────────────
    def on_close(self, handler):
        """ลงทะเบียน handler ตอนปิดโปรแกรม — เรียก handler() ตัวสุดท้ายต้องปิดจริง."""
        self._close_handlers.append(handler)

    def request_close(self):
        for handler in list(self._close_handlers):
            try:
                handler()
            except Exception:
                pass
        self.destroy()

    def destroy(self):
        try:
            self.win._force_close = True
            self.win.close()
            self.app.quit()
        except Exception:
            pass

    # ── Mainloop ─────────────────────────────────────────
    def run(self):
        self.win.show()
        self.app.exec()

    def after(self, ms, func):
        return QTimer.singleShot(ms, func)

    def process_events(self):
        self.app.processEvents()
