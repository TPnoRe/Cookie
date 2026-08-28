"""Viewport — ค้นหา Child Viewport (Render Window Handle) ของโปรแกรมจำลองอัตโนมัติ (Auto-Detection).

รองรับ Auto-Detect และระบุโปรแกรมจำลอง:
- LDPlayer   : Class "RenderWindow", "LDPlayerMainFrame" / Title "TheRender", "LDPlayer", "dnplayer"
- MuMu Player: Class "subWin", "ScreenUnseenWnd", "Qt5QWindowIcon" / Title "sub", "MuMu", "Nemu", "MuMuPlayer"
- NoxPlayer  : Class "RenderWindow", "subWin", "Qt5QWindowIcon" / Title "Nox", "NoxPlayer"
- BlueStacks : Class "RenderWindow", "subWin", "BlueStacksApp" / Title "BlueStacks", "HD-Player"
- MEmu Play  : Class "RenderWindow", "subWin" / Title "MEmu", "MEmuPlayer"

ป้องกันการเชื่อมต่อก่อนเวลา (Premature 0x0):
- ตรวจสอบขนาดพื้นที่แสดงผลจริง (Width >= 200, Height >= 200) ก่อนยืนยันการเชื่อมต่อ
- หาก Emulator อยู่ระหว่างการบูต (Loading Screen) จะรอจนกว่า Render Surface จะพร้อมแสดงผล
"""
import threading
import win32gui


class ViewportNotFoundError(Exception):
    pass


EMULATOR_PROFILES = [
    {
        'id': 'ldplayer',
        'name': 'LDPlayer',
        'aliases': ('ld', 'ldplayer', 'ldplayer9', 'dnplayer'),
        'classes': ('RenderWindow',),      # เฉพาะ Child Render Surface ไม่รวม Titlebar
        'titles': ('TheRender',),          # Title "TheRender" = render surface จริงของ LDPlayer
    },
    {
        'id': 'mumu',
        'name': 'MuMu Player',
        'aliases': ('mumu', 'mumu player', 'mumuplayer', 'nemu'),
        'classes': ('subWin', 'ScreenUnseenWnd', 'Qt5QWindowIcon'),
        'titles': ('sub', 'MuMu', 'Nemu', 'MuMuPlayer'),
    },
    {
        'id': 'nox',
        'name': 'NoxPlayer',
        'aliases': ('nox', 'noxplayer', 'nox app player'),
        'classes': ('RenderWindow', 'subWin', 'Qt5QWindowIcon'),
        'titles': ('Nox', 'NoxPlayer'),
    },
    {
        'id': 'bluestacks',
        'name': 'BlueStacks',
        'aliases': ('blue', 'bluestacks', 'bluestacks 5', 'bluestacks x', 'hd-player'),
        'classes': ('RenderWindow', 'subWin', 'BlueStacksApp', 'Qt5QWindowIcon'),
        'titles': ('BlueStacks', 'HD-Player'),
    },
    {
        'id': 'memu',
        'name': 'MEmu Play',
        'aliases': ('memu', 'memuplay', 'memu play'),
        'classes': ('RenderWindow', 'subWin'),
        'titles': ('MEmu', 'MEmuPlayer'),
    },
]

_EXCLUDE_TITLES = ('Cookie Run', 'Cookie Run Classic Bot', 'Visual Studio', 'Code')


class Viewport:
    """ค้นหาและเก็บ Window Handle ของพื้นที่แสดงผลเกม (Child Viewport) พร้อม Auto Detection."""

    def __init__(self):
        self._lock = threading.Lock()
        self.hwnd = None
        self.connected = False
        self.error = None
        self.detected_name = None

    # ── ค้นหา Render Window ─────────────────────────────
    @staticmethod
    def _matches_profile(cls, title, profile):
        classes = profile.get('classes', ())
        titles = profile.get('titles', ())
        cls_lower = cls.lower()
        title_lower = title.lower()
        if any(c.lower() in cls_lower for c in classes):
            return True
        for t in titles:
            if t.lower() in title_lower:
                return True
        return False

    def _get_target_profiles(self, target='auto'):
        t_clean = str(target).strip().lower()
        if t_clean in ('auto', 'auto detect', 'autodetect', 'all', '', 'custom adb'):
            return EMULATOR_PROFILES

        for p in EMULATOR_PROFILES:
            if t_clean == p['id'] or t_clean in p['aliases'] or p['name'].lower() in t_clean:
                return [p]

        return EMULATOR_PROFILES

    def _find(self, target='auto'):
        target_profiles = self._get_target_profiles(target)
        found_matches = []

        def enum_top(hwnd, param):
            try:
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd)
                if any(ex in title for ex in _EXCLUDE_TITLES):
                    return True
                # ค้นหา child render window เท่านั้น — ไม่รวม top-level window (มี titlebar/toolbar)
                win32gui.EnumChildWindows(hwnd, lambda ch, _: enum_child_all(ch), None)
            except Exception:
                pass
            return True

        def enum_child_all(hwnd):
            try:
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    return True
                cls = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                if any(ex in title for ex in _EXCLUDE_TITLES):
                    return True
                for prof in target_profiles:
                    if self._matches_profile(cls, title, prof):
                        left, top, right, bottom = win32gui.GetClientRect(hwnd)
                        w, h = right - left, bottom - top
                        if w >= 200 and h >= 200:
                            found_matches.append((hwnd, prof['name'], w * h))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_top, None)
        except Exception:
            pass

        if found_matches:
            # เลือก child render window ที่มีพื้นที่ viewport ใหญ่ที่สุด (ไม่รวม titlebar)
            found_matches.sort(key=lambda x: x[2], reverse=True)
            best_hwnd, emu_name, _ = found_matches[0]
            self.detected_name = emu_name
            return best_hwnd

        self.detected_name = None
        return None

    def connect(self, target='auto'):
        with self._lock:
            hwnd = self._find(target)
            if hwnd:
                self.hwnd = hwnd
                self.connected = True
                size = self.get_size()
                if size and size[0] >= 200 and size[1] >= 200:
                    self.error = None
                    return True
                # หากหน้าจอยังเป็น 0x0 (ระหว่างบูต emulator) ให้ถือว่ายังไม่พร้อม
                self.hwnd = None
                self.connected = False
                self.detected_name = None
                self.error = 'โปรแกรมจำลองกำลังบูตระบบ (รอยืนยันขนาดหน้าจอแสดงผล)'
                return False

            self.hwnd = None
            self.connected = False
            self.detected_name = None
            self.error = 'ไม่พบโปรแกรมจำลอง (Auto Detect: LDPlayer, MuMu, Nox, BlueStacks, MEmu)'
            return False

    def disconnect(self):
        with self._lock:
            self.hwnd = None
            self.connected = False
            self.error = None
            self.detected_name = None

    # ── ขนาด Viewport ──────────────────────────────────
    def _is_window_alive(self, hwnd):
        """ตรวจสอบว่าหน้าต่างยังมีอยู่จริงและแสดงอยู่."""
        try:
            return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        except Exception:
            return False

    def get_size(self):
        """อ่านขนาดพื้นที่แสดงผลจริง (Width, Height) จาก GetClientRect."""
        if not self.connected or not self.hwnd:
            return None
        if not self._is_window_alive(self.hwnd):
            self.disconnect()
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            width, height = right - left, bottom - top
            if width >= 100 and height >= 100:
                return width, height
        except Exception:
            pass
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width, height = right - left, bottom - top
            if width >= 100 and height >= 100:
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

