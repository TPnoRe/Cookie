"""Tap — ระบบกดคลิกแบบ Background Click ผ่าน Win32 PostMessage.

ใช้ GetClientRect อ่านขนาดจอปัจจุบัน → แปลง % → PostMessage WM_LBUTTONDOWN/UP
รองรับ:
  - smooth mouse path เลียนแบบนิ้วมือมนุษย์ (Bezier curve)
  - jitter, delay กด, hold ค้าง แบบ random
  - SendMessage fallback หากปุ่มไม่ตอบสนอง
  - tap_reliable สำหรับปุ่มสำคัญ (เช่น Start Game)
"""
import random
import time
import math
import ctypes
import logging

import win32con
import win32gui

from emulator.coords import pct_to_px, px_to_pct
from emulator.overlay import get_overlay

log = logging.getLogger(__name__)

# Win32 SendMessage (synchronous)
_user32 = ctypes.windll.user32


def _send_message(hwnd, msg, wparam, lparam):
    """SendMessage — synchronous (รอให้หน้าต่างรับก่อน)."""
    return _user32.SendMessageW(hwnd, msg, wparam, lparam)


def _make_lparam(cx, cy):
    return ((int(cy) & 0xFFFF) << 16) | (int(cx) & 0xFFFF)


def _ease_inout(t):
    """Smooth ease-in-out เลียนแบบนิ้วมนุษย์."""
    return t * t * (3 - 2 * t)


class TapEngine:
    """เครื่องยนต์กดคลิก — รับ hwnd + settings แล้วทำการกด."""

    def __init__(self, hwnd=None, get_settings=None):
        self.hwnd = hwnd
        self._get_settings = get_settings or (lambda: {})
        self.last_tap_x = None
        self.last_tap_y = None
        # ตำแหน่ง cursor ล่าสุด (px) สำหรับ smooth path
        self._cursor_x = 0
        self._cursor_y = 0

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

    # ── Smooth mouse path (Bezier curve) ─────────────────────────────────
    def _move_smooth(self, from_x, from_y, to_x, to_y, steps=6, total_ms=60):
        """เลื่อนเมาส์จาก (from) ไป (to) แบบ Quadratic Bezier เลียนแบบนิ้วมนุษย์."""
        if not self.hwnd:
            return
        # midpoint arc เล็กน้อย
        mid_x = (from_x + to_x) / 2 + random.uniform(-6, 6)
        mid_y = (from_y + to_y) / 2 + random.uniform(-6, 6)
        delay_per_step = (total_ms / 1000.0) / max(steps, 1)
        for i in range(1, steps + 1):
            t = _ease_inout(i / steps)
            inv = 1 - t
            bx = inv * inv * from_x + 2 * inv * t * mid_x + t * t * to_x
            by = inv * inv * from_y + 2 * inv * t * mid_y + t * t * to_y
            lparam = _make_lparam(int(bx), int(by))
            try:
                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            except Exception:
                pass
            time.sleep(delay_per_step)
        self._cursor_x = to_x
        self._cursor_y = to_y

    # ── Core low-level down/up ────────────────────────────────────────────
    def _do_tap(self, cx, cy, hold_sec, use_send=False):
        """ส่ง LBUTTONDOWN/UP ไปยัง hwnd."""
        lparam = _make_lparam(cx, cy)
        try:
            if use_send:
                _send_message(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
                _send_message(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                time.sleep(hold_sec)
                _send_message(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            else:
                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
                win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                time.sleep(hold_sec)
                win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception as e:
            log.debug('_do_tap error: %s', e)
            return False

    # ── Tap by % ─────────────────────────────────────────────────────────
    def tap(self, x_pct, y_pct, hold_ms=None):
        """แตะที่พิกัด % ของ Viewport พร้อม smooth path + human jitter."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size

        s = self._settings()
        # Jitter % + px
        jitter_pct = float(s.get('click_jitter_pct', 0.5))
        dx = random.uniform(-jitter_pct, jitter_pct)
        dy = random.uniform(-jitter_pct, jitter_pct)
        cx, cy = pct_to_px(width, height, x_pct + dx, y_pct + dy)
        jitter_px = float(s.get('click_jitter_px', 1.5))
        cx = max(0, min(width - 1, int(cx + random.uniform(-jitter_px, jitter_px))))
        cy = max(0, min(height - 1, int(cy + random.uniform(-jitter_px, jitter_px))))

        # Pre-click delay (เลียนแบบเตรียมนิ้ว)
        delay_min = float(s.get('click_delay_min', 0.04))
        delay_max = float(s.get('click_delay_max', 0.12))
        if delay_max > delay_min:
            time.sleep(random.uniform(delay_min, delay_max))
        elif delay_min > 0:
            time.sleep(delay_min)

        # Smooth path
        smooth_steps = int(s.get('smooth_steps', 6))
        smooth_ms = float(s.get('smooth_ms', 60))
        self._move_smooth(self._cursor_x, self._cursor_y, cx, cy,
                          steps=smooth_steps, total_ms=smooth_ms)

        # Hold time random ± 20%
        if hold_ms is None:
            raw_hold = float(s.get('click_hold', 0.08))
            hold_sec = raw_hold if raw_hold <= 1.0 else raw_hold / 1000.0
        else:
            hold_sec = float(hold_ms) if float(hold_ms) <= 1.0 else float(hold_ms) / 1000.0
        hold_sec = max(0.05, hold_sec * random.uniform(0.85, 1.2))

        self.last_tap_x = cx
        self.last_tap_y = cy
        log.debug('tap @ (%d, %d) hold=%.3fs', cx, cy, hold_sec)

        ok = self._do_tap(cx, cy, hold_sec, use_send=False)

        overlay = get_overlay()
        if overlay:
            overlay.show_touch_hwnd(self.hwnd, cx, cy)
        return ok

    # ── Tap Reliable ─────────────────────────────────────────────────────
    def tap_reliable(self, x_pct, y_pct, hold_ms=None, confirm_delay=0.15):
        """กดแบบ reliable — PostMessage + SendMessage fallback + double-tap.

        ใช้กับปุ่มสำคัญ เช่น Start Game ที่กดพลาดไม่ได้.
        """
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size
        s = self._settings()

        jitter_pct = float(s.get('click_jitter_pct', 0.5))
        jitter_px = float(s.get('click_jitter_px', 1.5))

        def _calc_pos(extra_jit=0.0):
            dx = random.uniform(-jitter_pct, jitter_pct)
            dy = random.uniform(-jitter_pct, jitter_pct)
            px0, py0 = pct_to_px(width, height, x_pct + dx, y_pct + dy)
            jit = jitter_px + extra_jit
            px0 = max(0, min(width - 1, int(px0 + random.uniform(-jit, jit))))
            py0 = max(0, min(height - 1, int(py0 + random.uniform(-jit, jit))))
            return px0, py0

        if hold_ms is None:
            raw_hold = float(s.get('click_hold', 0.10))
            hold_sec = raw_hold if raw_hold <= 1.0 else raw_hold / 1000.0
        else:
            hold_sec = float(hold_ms) if float(hold_ms) <= 1.0 else float(hold_ms) / 1000.0
        hold_sec = max(0.08, hold_sec)

        delay_min = float(s.get('click_delay_min', 0.04))
        delay_max = float(s.get('click_delay_max', 0.12))
        if delay_max > delay_min:
            time.sleep(random.uniform(delay_min, delay_max))

        # — Tap 1: PostMessage —
        cx, cy = _calc_pos()
        self._move_smooth(self._cursor_x, self._cursor_y, cx, cy, steps=6, total_ms=50)
        self.last_tap_x, self.last_tap_y = cx, cy
        ok1 = self._do_tap(cx, cy, hold_sec, use_send=False)
        log.debug('tap_reliable PostMsg @ (%d, %d)', cx, cy)

        # Pause ให้เกมประมวลผล
        time.sleep(max(0.08, confirm_delay * random.uniform(0.9, 1.1)))

        # — Tap 2: SendMessage (synchronous) ตำแหน่งต่างกันนิดหน่อย —
        cx2, cy2 = _calc_pos(extra_jit=0.8)
        self._move_smooth(cx, cy, cx2, cy2, steps=4, total_ms=30)
        self.last_tap_x, self.last_tap_y = cx2, cy2
        ok2 = self._do_tap(cx2, cy2, hold_sec * random.uniform(0.9, 1.3), use_send=True)
        log.debug('tap_reliable SendMsg @ (%d, %d)', cx2, cy2)

        overlay = get_overlay()
        if overlay:
            overlay.show_touch_hwnd(self.hwnd, cx2, cy2)
        return ok1 or ok2

    # ── Tap by px ─────────────────────────────────────────────────────────
    def tap_px(self, x, y, hold_ms=0):
        """แตะที่พิกัดพิกเซลภายใน Viewport."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size
        s = self._settings()
        jit = float(s.get('click_jitter_px', 1.5))
        cx = max(0, min(width - 1, int(x + random.uniform(-jit, jit))))
        cy = max(0, min(height - 1, int(y + random.uniform(-jit, jit))))

        delay_min = float(s.get('click_delay_min', 0.04))
        delay_max = float(s.get('click_delay_max', 0.12))
        if delay_max > delay_min:
            time.sleep(random.uniform(delay_min, delay_max))
        elif delay_min > 0:
            time.sleep(delay_min)

        self._move_smooth(self._cursor_x, self._cursor_y, cx, cy, steps=5, total_ms=50)

        hold_sec = max(0.05, float(hold_ms) / 1000.0 if hold_ms > 0 else 0.07)
        hold_sec *= random.uniform(0.85, 1.15)

        self.last_tap_x = cx
        self.last_tap_y = cy

        ok = self._do_tap(cx, cy, hold_sec, use_send=False)
        overlay = get_overlay()
        if overlay:
            overlay.show_touch_hwnd(self.hwnd, cx, cy)
        return ok

    # ── Tap Fast (gameplay — ไม่มี smooth path เพื่อความเร็ว) ─────────────
    def tap_fast(self, x_pct, y_pct):
        """กดเร็ว — delay 0.03-0.08s, hold 40-70ms."""
        if not self.hwnd:
            return False
        size = self._get_size()
        if not size:
            return False
        width, height = size
        cx, cy = pct_to_px(width, height, x_pct, y_pct)
        try:
            time.sleep(random.uniform(0.03, 0.08))
            hold_sec = random.uniform(0.04, 0.07)
            lparam = _make_lparam(cx, cy)
            self.last_tap_x = cx
            self.last_tap_y = cy
            log.debug('tap_fast @ (%d, %d)', cx, cy)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(hold_sec)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception:
            return False

    # ── Direct Win32 (static helper) ──────────────────────────────────────
    @staticmethod
    def click_percent(render_hwnd, x_pct, y_pct):
        """กดคลิกแบบตัวอย่าง — GetClientRect + PostMessage โดยตรง."""
        rect = win32gui.GetClientRect(render_hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        cx = int(width * x_pct / 100.0)
        cy = int(height * y_pct / 100.0)
        lparam = (cy << 16) | cx
        win32gui.PostMessage(render_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)
        win32gui.PostMessage(render_hwnd, win32con.WM_LBUTTONUP, 0, lparam)