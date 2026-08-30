"""Client — Emulator client: จับหน้าจอ + คลิกด้วย Win32 API.

Viewport ใช้ Child Render Window Handle (ข้ามแถบเมนู/ขอบหน้าต่างภายนอก)
Capture: PrintWindow (fallback: BitBlt / ImageGrab)
คลิก:    PostMessage WM_LBUTTONDOWN/UP ที่พิกัด % ของ Viewport
"""
import base64
import io
import threading
import time

import win32con
import win32gui
import win32ui
from ctypes import windll
from PIL import Image, ImageGrab

from emulator.viewport import Viewport
from emulator.tap import TapEngine
from emulator.coords import px_to_pct


class EmulatorClient:
    """ตัวควบคุมโปรแกรมจำลอง — ใช้พิกัด % สเกลตามขนาดจอปัจจุบันเสมอ."""

    def __init__(self, get_settings=None):
        self._get_settings = get_settings or (lambda: {})
        self._lock = threading.Lock()
        self.viewport = Viewport()
        self.tap_engine = TapEngine(get_settings=self._get_settings)
        self.connected = False
        self.error = None
        self.last_click = None
        self.last_size = None

    @property
    def hwnd(self):
        return self.viewport.hwnd

    @property
    def emulator_name(self):
        return self.viewport.detected_name or 'Emulator'

    # ── Connect ─────────────────────────────────────────
    def connect(self, target='auto'):
        with self._lock:
            settings = self._get_settings() or {}
            target = target if target != 'auto' else settings.get(
                'emulator', 'auto')
            ok = self.viewport.connect(target)
            self.connected = self.viewport.connected
            self.error = self.viewport.error
            self.tap_engine.hwnd = self.viewport.hwnd
            if ok:
                self.last_size = self.get_size()
            return ok

    def disconnect(self):
        with self._lock:
            self.viewport.disconnect()
            self.tap_engine.hwnd = None
            self.connected = False
            self.error = None

    def is_alive(self):
        """ตรวจสอบว่าหน้าต่าง Emulator ยังทำงานอยู่จริงหรือไม่."""
        if not self.connected or not self.viewport.hwnd:
            return False
        return self.viewport._is_window_alive(self.viewport.hwnd)

    # ── Size ────────────────────────────────────────────
    def get_size(self):
        size = self.viewport.get_size()
        self.connected = self.viewport.connected
        if size:
            self.last_size = size
        return size

    # ── Capture ─────────────────────────────────────────

    def screenshot(self):
        # The bot worker and preview UI can request a frame concurrently.
        # Serialize capture and always release GDI handles on every path.
        with self._lock:
            if not self.connected or not self.hwnd:
                return None
            hwnd = self.hwnd
            size = self.get_size()
            self.connected = self.viewport.connected
            if not size:
                return None
            width, height = size

            for flag in (3, 0):
                img = self._capture_gdi(hwnd, width, height, print_flag=flag)
                if img:
                    return img

            img = self._capture_gdi(hwnd, width, height, print_flag=None)
            if img:
                return img

            try:
                sx, sy = self.viewport.client_to_screen(0, 0)
                img = ImageGrab.grab(bbox=(sx, sy, sx + width, sy + height))
                return img.copy() if img else None
            except Exception:
                return None

    @staticmethod
    def _capture_gdi(hwnd, width, height, print_flag):
        """Capture one frame and release every GDI resource, even on failure."""
        hwnd_dc = mfc_dc = save_dc = bitmap = old_bitmap = None
        try:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            old_bitmap = save_dc.SelectObject(bitmap)

            if print_flag is None:
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0),
                               win32con.SRCCOPY)
            elif windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_flag) != 1:
                return None

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1).copy()
            return img if img.width > 0 and img.height > 0 else None
        except Exception:
            return None
        finally:
            if save_dc is not None and old_bitmap is not None:
                try:
                    save_dc.SelectObject(old_bitmap)
                except Exception:
                    pass
            if bitmap is not None:
                try:
                    win32gui.DeleteObject(bitmap.GetHandle())
                except Exception:
                    pass
            if save_dc is not None:
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
            if mfc_dc is not None:
                try:
                    mfc_dc.DeleteDC()
                except Exception:
                    pass
            if hwnd_dc is not None:
                try:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
                except Exception:
                    pass

    def screenshot_base64(self):
        img = self.screenshot()
        if not img:
            return None
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')

    # ── Click ───────────────────────────────────────────
    def tap(self, x_pct, y_pct, hold_ms=None, box_w_pct=None, box_h_pct=None):
        """Tap a point, optionally randomised within its coordinate box."""
        if not self.connected or not self.hwnd:
            return False
        size = self.get_size()
        if not size:
            return False
        ok = self.tap_engine.tap(
            x_pct, y_pct, hold_ms, box_w_pct=box_w_pct, box_h_pct=box_h_pct)
        if ok:
            width, height = size
            ax = self.tap_engine.last_tap_x
            ay = self.tap_engine.last_tap_y
            if ax is not None and ay is not None:
                self.last_click = (
                    round(ax / width * 100.0, 2),
                    round(ay / height * 100.0, 2),
                    time.time(),
                )
            else:
                from emulator.coords import pct_to_px
                cx, cy = pct_to_px(width, height, x_pct, y_pct)
                self.last_click = (
                    round(cx / width * 100.0, 2),
                    round(cy / height * 100.0, 2),
                    time.time(),
                )
        return ok

    def tap_px(self, x, y, hold_ms=0):
        """แตะที่พิกัดพิกเซลภายใน Viewport."""
        if not self.connected or not self.hwnd:
            return False
        size = self.get_size()
        if not size:
            return False
        ok = self.tap_engine.tap_px(x, y, hold_ms)
        if ok:
            width, height = size
            self.last_click = px_to_pct(width, height, x, y) + (
                time.time(),)
        return ok

    def tap_fast(self, x_pct, y_pct, box_w_pct=None, box_h_pct=None):
        """Fast tap, optionally randomised within its coordinate box."""
        if not self.connected or not self.hwnd:
            return False
        size = self.get_size()
        if not size:
            return False
        ok = self.tap_engine.tap_fast(
            x_pct, y_pct, box_w_pct=box_w_pct, box_h_pct=box_h_pct)
        if ok:
            width, height = size
            ax = self.tap_engine.last_tap_x
            ay = self.tap_engine.last_tap_y
            if ax is not None and ay is not None:
                self.last_click = (
                    round(ax / width * 100.0, 2),
                    round(ay / height * 100.0, 2),
                    time.time(),
                )
        return ok
