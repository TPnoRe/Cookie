"""Responsive helpers — คุมการยืด/หดของ widget ด้วย layout stretch (PyQt6).

ใช้เพื่อให้ทุกหน้า (Dashboard / Settings / Coordinates) ปรับขนาดเอง
เมื่อหน้าต่างถูกย่อ/ขยาย โดยไม่ต้องเขียน setColumnStretch ซ้ำ ๆ
"""
from PyQt6.QtWidgets import QGridLayout


def make_grid(frame, columns=1, rows=1, col_weights=None, row_weights=None):
    """กำหนด stretch ของคอลัมน์/แถวใน QGridLayout ของ frame.

    frame          : widget ที่มี QGridLayout หรือตัว QGridLayout เอง
    columns/rows   : จำนวนคอลัมน์/แถวที่จะตั้งค่า
    col_weights    : list เช่น [6, 4] → คอลัมน์ 0 กว้าง 60%, คอลัมน์ 1 กว้าง 40%
    row_weights    : list เช่น [0, 1] → แถว 0 พอดีเนื้อหา, แถว 1 ยืดเต็มที่
    """
    if isinstance(frame, QGridLayout):
        layout = frame
    else:
        layout = frame.layout()
        if layout is None:
            layout = QGridLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
    for c in range(columns):
        layout.setColumnStretch(
            c, col_weights[c] if col_weights and c < len(col_weights) else 1)
    for r in range(rows):
        layout.setRowStretch(
            r, row_weights[r] if row_weights and r < len(row_weights) else 1)
    return layout
