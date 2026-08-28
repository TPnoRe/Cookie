"""Tap — ระบบกดคลิกแบบ Background Click ผ่าน Win32 PostMessage.

ใช้ GetClientRect อ่านขนาดจอปัจจุบัน → แปลง % → PostMessage WM_LBUTTONDOWN/UP
รองรับ jitter, delay กด, hold ค้าง, ตั้งค่าผ่าน settings
"""
import random
import time
import logging

import win32con
import win32gui

from emulator.coords import pct_to_px, px_to_pct
from emulator.overlay import get_overlay

log = logging.getLogger(__name__)


class TapEngine:
    """เครื่องยนต์กดคลิก — รับ hwnd + settings แล้วทำการกด."""

    def __init__(self, hwnd=None, get_settings=None):
        self.hwnd = hwnd
        self._get_settings = get_settings or (lambda: {})
        self.last_tap_x = None
        self.last_tap_y = None

    def _settings(self):
        return self._get_settings() or {}

    def _get_size(self):
        if not self.hwnd:
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            w, h = right - left, bottom - top
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
        return None

    # ── Tap by % ───────────────────────────────────────
    def tap(self, x_pct, y_pct, hold_ms=None):
        """แตะที่พิกัด % ของ Viewport."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size

        s = self._settings()
        jitter_pct = float(s.get('click_jitter_pct', 0.2))
        dx = random.uniform(-jitter_pct, jitter_pct)
        dy = random.uniform(-jitter_pct, jitter_pct)
        cx, cy = pct_to_px(width, height, x_pct + dx, y_pct + dy)

        jitter_px = float(s.get('click_jitter_px', 0.5))
        cx = max(0, min(width - 1, int(cx + random.uniform(-jitter_px, jitter_px))))
        cy = max(0, min(height - 1, int(cy + random.uniform(-jitter_px, jitter_px))))

        delay_min = float(s.get('click_delay_min', 0.05))
        delay_max = float(s.get('click_delay_max', 0.15))
        if delay_max > delay_min:
            time.sleep(random.uniform(delay_min, delay_max))
        elif delay_min > 0:
            time.sleep(delay_min)

        if hold_ms is None:
            raw_hold = float(s.get('click_hold', 0.10))
            hold_sec = raw_hold if raw_hold <= 1.0 else raw_hold / 1000.0
        else:
            hold_sec = float(hold_ms) if float(hold_ms) <= 1.0 else float(hold_ms) / 1000.0

        hold_sec = max(0.08, hold_sec)

        try:
            lparam = ((int(cy) & 0xFFFF) << 16) | (int(cx) & 0xFFFF)
            self.last_tap_x = cx
            self.last_tap_y = cy
            log.debug('tap @ (%d, %d)' % (cx, cy))
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            win32gui.PostMessage(
                self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(hold_sec)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)

            # แสดงเอฟเฟกต์วงแหวนแตะจอ (Touch Overlay)
            overlay = get_overlay()
            if overlay:
                overlay.show_touch_hwnd(self.hwnd, cx, cy)

            return True
        except Exception:
            return False

    # ── Tap by px ──────────────────────────────────────
    def tap_px(self, x, y, hold_ms=0):
        """แตะที่พิกัดพิกเซลภายใน Viewport."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size
        s = self._settings()
        jit = float(s.get('click_jitter_px', 0.5))
        cx = max(0, min(width - 1, int(x + random.uniform(-jit, jit))))
        cy = max(0, min(height - 1, int(y + random.uniform(-jit, jit))))

        delay_min = float(s.get('click_delay_min', 0.05))
        delay_max = float(s.get('click_delay_max', 0.15))
        if delay_max > delay_min:
            time.sleep(random.uniform(delay_min, delay_max))
        elif delay_min > 0:
            time.sleep(delay_min)

        hold_sec = max(0.08, float(hold_ms) / 1000.0 if hold_ms > 0 else 0.08)

        try:
            lparam = ((int(cy) & 0xFFFF) << 16) | (int(cx) & 0xFFFF)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            win32gui.PostMessage(
                self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(hold_sec)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)

            # แสดงเอฟเฟกต์วงแหวนแตะจอ (Touch Overlay)
            overlay = get_overlay()
            if overlay:
                overlay.show_touch_hwnd(self.hwnd, cx, cy)

            return True
        except Exception:
            return False

    # ── Direct Win32 (ตัวอย่าง) ────────────────────────
    @staticmethod
    def click_percent(render_hwnd, x_pct, y_pct):
        """กดคลิกแบบตัวอย่าง — GetClientRect + PostMessage โดยตรง."""
        rect = win32gui.GetClientRect(render_hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        cx = int(width * x_pct / 100.0)
        cy = int(height * y_pct / 100.0)
        lparam = (cy << 16) | cx
        win32gui.PostMessage(
            render_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)
        win32gui.PostMessage(render_hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        
    # ── Tap Fast (delay สั้น) ──
    def tap_fast(self, x_pct, y_pct):
        """กดเร็ว — delay 0.05-0.10s, hold 80ms."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size
        cx, cy = pct_to_px(width, height, x_pct, y_pct)
        try:
            time.sleep(random.uniform(0.05, 0.10))
            lparam = ((int(cy) & 0xFFFF) << 16) | (int(cx) & 0xFFFF)
            self.last_tap_x = cx
            self.last_tap_y = cy
            log.debug('tap_fast @ (%d, %d)' % (cx, cy))
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            win32gui.PostMessage(
                self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(0.08)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception:
            return False