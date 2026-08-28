"""Dropdown — ระบบ dropdown สำเร็จรูปสำหรับ UI (PyQt6).

Drop-in replacement สำหรับ QComboBox ที่ปรับแต่งสี/ฟอนต์ได้ทั้งหมด.

ใช้งาน:
    from ui.dropdown import Dropdown

    dd = Dropdown(parent, items=[
        ('gold', 'Farm Gold'),
        ('exp', 'Farm EXP'),
        '---',
        ('box', 'Farm Box', None, 'No jump mode'),
    ])
    dd.set_current('gold')
    dd.current_changed.connect(on_change)
"""
from ui.dropdown.dropdown import Dropdown

__all__ = ['Dropdown']
