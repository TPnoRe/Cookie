"""Viewport — ค้นหา Child Viewport (Render Window Handle) ของโปรแกรมจำลอง.

รองรับ:
- LDPlayer   : Class "RenderWindow" / Title "TheRender"
- MuMu Player: Class "subWin" / Title "sub"

ใช้ win32gui.GetClientRect(render_hwnd) อ่านขนาดพื้นที่แสดงผลเกมจริงแบบเรียลไทม์
เพื่อให้บอทอ้างอิงขนาดจอปัจจุบันตลอดเวลา (ไม่ตายตัว 1280x720)
"""
import threading

import win32gui


class ViewportNotFoundError(Exception):
    pass


VIEWPORT_MATCHERS = {
    'ldplayer': (('RenderWindow',), ('TheRender', 'LDPlayer')),
    'mumu': (('subWin', 'ScreenUnseenWnd'), ('sub', 'MuMu', 'Nemu')),
    'nox': (('RenderWindow', 'subWin'), ('Nox',)),
    'memu': (('RenderWindow', 'subWin'), ('MEmu',)),
    'bluestacks': (('RenderWindow', 'subWin'), ('BlueStacks',)),
    'auto': (('RenderWindow', 'subWin', 'ScreenUnseenWnd'),
             ('TheRender', 'sub', 'MuMu', 'Nemu', 'LDPlayer')),
}


class Viewport:
    """ค้นหาและเก็บ Window Handle ของพื้นที่แสดงผลเกม (Child Viewport)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.hwnd = None
        self.connected = False
        self.error = None

    # ── ค้นหา Render Window ─────────────────────────────
    def _matches(self, cls, title, matchers):
        classes, titles = matchers
        if cls in classes:
            return True
        for t in titles:
            if t in title:
                return True
        return False

    def _find(self, target='auto'):
        matchers = VIEWPORT_MATCHERS.get(
            str(target).lower(), VIEWPORT_MATCHERS['auto'])

        found = []

        def enum_child(hwnd, param):
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if self._matches(cls, title, matchers):
                found.append(hwnd)
            return True

        def enum_top(hwnd, param):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            win32gui.EnumChildWindows(hwnd, enum_child, None)
            return True

        win32gui.EnumWindows(enum_top, None)
        if found:
            return found[0]

        # Fallback
        def enum_all_child(hwnd, param):
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if self._matches(cls, title, matchers):
                found.append(hwnd)
            return True

        def enum_all_top(hwnd, param):
            win32gui.EnumChildWindows(hwnd, enum_all_child, None)
            return True

        win32gui.EnumWindows(enum_all_top, None)
        if found:
            return found[0]
        return None

    def connect(self, target='auto'):
        with self._lock:
            hwnd = self._find(target)
            if hwnd:
                self.hwnd = hwnd
                self.connected = True
                self.error = None
                return True
            self.hwnd = None
            self.connected = False
            self.error = 'ไม่พบหน้าต่างโปรแกรมจำลอง (LDPlayer / MuMu Player)'
            return False

    def disconnect(self):
        with self._lock:
            self.hwnd = None
            self.connected = False
            self.error = None

    # ── ขนาด Viewport ──────────────────────────────────
    def get_size(self):
        """อ่านขนาดพื้นที่แสดงผลจริง (Width, Height) จาก GetClientRect."""
        if not self.connected or not self.hwnd:
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            width, height = right - left, bottom - top
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width, height = right - left, bottom - top
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
        return None

    def client_to_screen(self, x_px, y_px):
        """แปลงพิกัดภายใน Viewport -> พิกัดจอ (ใช้กับ overlay)."""
        if not self.hwnd:
            return x_px, y_px
        try:
            return win32gui.ClientToScreen(self.hwnd, (int(x_px), int(y_px)))
        except Exception:
            return x_px, y_px

