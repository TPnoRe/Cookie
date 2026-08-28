"""Emulator — ระบบควบคุมโปรแกรมจำลอง (LDPlayer / MuMu Player / อื่น ๆ).

- viewport: ค้นหา Child Render Window Handle สำหรับจับขอบเขตจอเกมจริง
- coords:   ระบบพิกัดเปอร์เซ็นต์ (0-100%) สเกลตามขนาดจอปัจจุบัน
- tap:      TapEngine กดคลิกแบบ Background Click ผ่าน Win32 PostMessage
- client:   EmulatorClient จับหน้าจอ + คลิกผ่าน Win32 API
"""

from emulator.viewport import Viewport, ViewportNotFoundError
from emulator.tap import TapEngine
from emulator.client import EmulatorClient
from emulator import coords
from emulator.overlay import TouchOverlay, get_overlay

__all__ = ['Viewport', 'ViewportNotFoundError', 'TapEngine',
           'EmulatorClient', 'coords', 'TouchOverlay', 'get_overlay']
