"""emulator/overlay/touch_overlay.py — ระบบแสดงเอฟเฟกต์วงแหวนสัมผัส (Touch Indicator / Overlay)

แสดงวงแหวนเอฟเฟกต์ (Touch Ripple) ณ จุดที่บอทแตะพิกัดบนจอ Emulator
- แสดงผลเฉพาะภายในหน้าต่าง Emulator เท่านั้น
- ซ่อนอัตโนมัติเมื่อมีหน้าต่างโปรแกรมอื่นมาบัง (Occlusion Detection)
- ซ่อนอัตโนมัติเมื่อ Emulator ถูกย่อ (Minimized) หรืออยู่นอกจอ
- Thread-safe: รองรับการเรียกจาก Background Thread (Bot Thread) ผ่าน Qt Queued Signal
- Click-through & Never Steal Focus (ไม่แย่งโฟกัส ไม่ขวางการคลิก)
- อนิเมชันวงแหวนขยาย + เฟดโปร่งแสง (Fade out)
"""
import time
from typing import List, Optional
from PyQt6.QtCore import Qt, QTimer, QPoint, QObject, pyqtSignal, QRectF, QThread
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QApplication
import win32gui
import win32con


class _TouchSignalEmitter(QObject):
    """ตัวส่ง Signal ข้าม Thread ไปยัง Overlay Widget."""
    show_touch_requested = pyqtSignal(int, int, int, str, int)


class _TouchPoint:
    """ข้อมูลจุดสัมผัส 1 จุด พร้อมเวลา, HWND และอนิเมชัน."""
    def __init__(self, x: int, y: int, duration_ms: int = 400, color: str = '#00F0FF', hwnd: int = 0):
        self.x = x
        self.y = y
        self.duration = max(0.1, duration_ms / 1000.0)
        self.color = QColor(color)
        self.start_time = time.time()
        self.max_radius = 24.0
        self.hwnd = hwnd

    @property
    def progress(self) -> float:
        elapsed = time.time() - self.start_time
        return min(1.0, max(0.0, elapsed / self.duration))

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.start_time) < self.duration


class TouchOverlay(QWidget):
    """หน้าต่าง Overlay โปร่งแสง แสดงจุดที่แตะพิกัด เฉพาะบนหน้าต่าง Emulator."""

    def __init__(self):
        super().__init__(None)
        self._touches: List[_TouchPoint] = []
        self._emitter = _TouchSignalEmitter()
        self._emitter.show_touch_requested.connect(self._on_show_touch, Qt.ConnectionType.QueuedConnection)
        self._emulator_hwnd = 0

        # ตั้งค่า Window flags: ไม่แสดงบน taskbar, อยู่บนสุดเสมอ, ไม่มีกรอบ, ไม่รับเมาส์
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.setGeometry(0, 0, 1, 1)

        # Timer สำหรับ Animation Loop 60fps
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_animate)

    def _setup_win32_ex_styles(self):
        """ตั้งค่า Win32 Extended Styles เพื่อให้คลิกทะลุ 100% (Click-Through) และไม่แย่งโฟกัส."""
        try:
            hwnd = int(self.winId())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= (
                win32con.WS_EX_TRANSPARENT
                | win32con.WS_EX_LAYERED
                | win32con.WS_EX_TOOLWINDOW
                | win32con.WS_EX_NOACTIVATE
            )
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        except Exception:
            pass

    def _update_geometry(self, hwnd=0):
        """ขยาย Overlay ให้ครอบเฉพาะ client area ของ Emulator."""
        if hwnd:
            self._emulator_hwnd = hwnd
        try:
            h = self._emulator_hwnd or hwnd
            if h and win32gui.IsWindow(h):
                left, top, right, bottom = win32gui.GetClientRect(h)
                w, ht = right - left, bottom - top
                if w > 0 and ht > 0:
                    sx, sy = win32gui.ClientToScreen(h, (0, 0))
                    self.setGeometry(sx, sy, w, ht)
                    return
        except Exception:
            pass
        self.setGeometry(0, 0, 1, 1)

    def _is_occluded(self, hwnd: int, screen_x: int, screen_y: int) -> bool:
        """ตรวจสอบว่าตำแหน่ง (screen_x, screen_y) ถูกหน้าต่างโปรแกรมอื่นบดบังหรือไม่."""
        if not hwnd or not win32gui.IsWindow(hwnd):
            return True
        try:
            # ตรวจสอบสถานะการย่อหน้าต่าง (Minimized)
            if win32gui.IsIconic(hwnd):
                return True
            root_emu = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            if root_emu and win32gui.IsIconic(root_emu):
                return True

            # ตรวจสอบว่าหน้าต่างแสดงอยู่หรือไม่
            if not win32gui.IsWindowVisible(hwnd) or (root_emu and not win32gui.IsWindowVisible(root_emu)):
                return True

            # ตรวจสอบว่าตำแหน่งแตะอยู่ภายใน Client Area ของ Emulator หรือไม่
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            cw, ch = right - left, bottom - top
            cx, cy = win32gui.ScreenToClient(hwnd, (int(screen_x), int(screen_y)))
            if not (0 <= cx < cw and 0 <= cy < ch):
                return True

            # ตรวจสอบว่าหน้าต่างบนสุด ณ ตำแหน่งนี้เป็น Emulator หรือไม่
            top_hwnd = win32gui.WindowFromPoint((int(screen_x), int(screen_y)))
            if top_hwnd:
                top_root = win32gui.GetAncestor(top_hwnd, win32con.GA_ROOT)
                overlay_hwnd = int(self.winId()) if hasattr(self, 'winId') else 0
                # ถ้าหน้าต่างบนสุดไม่ใช่ Emulator, ไม่ใช่ Root ของ Emulator และไม่ใช่ตัว Overlay เอง
                if (top_hwnd != hwnd and top_root != root_emu and
                        top_hwnd != root_emu and top_hwnd != overlay_hwnd and top_root != overlay_hwnd):
                    return True  # มีหน้าต่างโปรแกรมอื่นบังอยู่
        except Exception:
            pass
        return False

    def show_touch_screen(self, screen_x: int, screen_y: int, duration_ms: int = 400, color: str = '#00F0FF', hwnd: int = 0):
        """ส่งคำขอแสดงจุดแตะพิกัดจอ (Thread-safe)."""
        try:
            self._emitter.show_touch_requested.emit(int(screen_x), int(screen_y), int(duration_ms), str(color), int(hwnd))
        except Exception:
            pass

    def show_touch_hwnd(self, hwnd: int, client_x: int, client_y: int, duration_ms: int = 400, color: str = '#00F0FF'):
        """ส่งคำขอแสดงจุดแตะจาก Client coordinate ของหน้าต่าง Emulator (Thread-safe)."""
        try:
            if hwnd and win32gui.IsWindow(hwnd):
                pt = win32gui.ClientToScreen(hwnd, (int(client_x), int(client_y)))
                self.show_touch_screen(pt[0], pt[1], duration_ms, color, hwnd)
                return
        except Exception:
            pass
        self.show_touch_screen(int(client_x), int(client_y), duration_ms, color, hwnd)

    def _on_show_touch(self, x: int, y: int, duration_ms: int, color: str, hwnd: int):
        """Slot ทำงานบน Main GUI Thread เท่านั้น."""
        try:
            if hwnd and self._is_occluded(hwnd, x, y):
                return
            self._update_geometry(hwnd)
            self._touches.append(_TouchPoint(x, y, duration_ms, color, hwnd))
            if not self.isVisible():
                self.show()
                self._setup_win32_ex_styles()
            if not self._anim_timer.isActive():
                self._anim_timer.start()
            self.update()
        except Exception:
            pass

    def _on_animate(self):
        """ลบจุดที่หมดอายุและสั่งวาดใหม่."""
        try:
            self._touches = [t for t in self._touches if t.is_alive]
            if not self._touches:
                self._anim_timer.stop()
                self.hide()
            self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        if not self._touches:
            return

        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            ox, oy = self.geometry().x(), self.geometry().y()

            for t in self._touches:

                p = t.progress
                cur_radius = 6.0 + (t.max_radius - 6.0) * (p ** 0.5)
                alpha = int(255 * (1.0 - p))
                if alpha <= 0:
                    continue

                lx = float(t.x - ox)
                ly = float(t.y - oy)

                # Solid Center Dot
                center_color = QColor(t.color)
                center_color.setAlpha(min(255, int(alpha * 1.2)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(center_color))
                painter.drawEllipse(QPoint(int(lx), int(ly)), 4, 4)

                # Inner Ripple
                inner_color = QColor(t.color)
                inner_color.setAlpha(alpha)
                pen = QPen(inner_color, 2.5)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(lx - cur_radius, ly - cur_radius, cur_radius * 2, cur_radius * 2))

                # Outer Glow
                outer_radius = cur_radius * 1.35
                glow_color = QColor(t.color)
                glow_color.setAlpha(int(alpha * 0.45))
                glow_pen = QPen(glow_color, 1.5)
                painter.setPen(glow_pen)
                painter.drawEllipse(QRectF(lx - outer_radius, ly - outer_radius, outer_radius * 2, outer_radius * 2))

            painter.end()
        except Exception:
            pass


# Singleton Instance
_overlay_instance = None


def init_overlay() -> TouchOverlay:
    """สร้าง Overlay บน Main GUI Thread."""
    global _overlay_instance
    if _overlay_instance is None:
        try:
            _overlay_instance = TouchOverlay()
        except Exception:
            pass
    return _overlay_instance


def get_overlay() -> Optional[TouchOverlay]:
    """คืนค่า Overlay instance อย่างปลอดภัย (ไม่สร้าง QWidget จาก background thread)."""
    global _overlay_instance
    if _overlay_instance is None:
        app = QApplication.instance()
        if app is not None and QThread.currentThread() == app.thread():
            try:
                _overlay_instance = TouchOverlay()
            except Exception:
                pass
    return _overlay_instance
