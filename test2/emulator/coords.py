"""Coords — ระบบพิกัดเปอร์เซ็นต์ (0-100%) แปลงตามขนาดจอปัจจุบันแบบไดนามิก.

เมื่อผู้ใช้ย่อ/ขยายหน้าจอโปรแกรมจำลอง (เช่น 1280x720 -> 1920x1080)
พิกัดที่เก็บเป็น % จะถูกสเกลใหม่ทุกครั้งจากขนาด Viewport ณ วินาทีนั้น:
    cx = int(width  * x_pct / 100.0)
    cy = int(height * y_pct / 100.0)
"""


def clamp(value, low, high):
    return max(low, min(high, value))


def pct_to_px(width, height, x_pct, y_pct):
    """แปลงพิกัด % -> พิกเซล (ปัด 0-ขอบเขตจอเสมอ)."""
    cx = int(float(x_pct) / 100.0 * width)
    cy = int(float(y_pct) / 100.0 * height)
    return clamp(cx, 0, max(0, width - 1)), clamp(cy, 0, max(0, height - 1))


def px_to_pct(width, height, x_px, y_px):
    """แปลงพิกัดพิกเซล -> % (สำหรับบันทึกค่าจากหน้าจอ)."""
    if not width or not height:
        return 0.0, 0.0
    x_pct = clamp(float(x_px) / width * 100.0, 0.0, 100.0)
    y_pct = clamp(float(y_px) / height * 100.0, 0.0, 100.0)
    return round(x_pct, 2), round(y_pct, 2)


def scale_rect(width, height, x_pct, y_pct, w_pct, h_pct):
    """แปลงกรอบพิกัด % (ศูนย์กลาง + W/H เป็น %) -> พิกเซล rect (x,y,w,h)."""
    cx, cy = pct_to_px(width, height, x_pct, y_pct)
    w = int(float(w_pct) / 100.0 * width)
    h = int(float(h_pct) / 100.0 * height)
    x = clamp(cx - w // 2, 0, max(0, width - 1))
    y = clamp(cy - h // 2, 0, max(0, height - 1))
    return x, y, w, h


def rect_to_pct(width, height, x, y, w, h):
    """แปลง rect พิกเซล -> % (ศูนย์กลาง x/y + W/H เป็น %)."""
    if not width or not height:
        return 0.0, 0.0, 0.0, 0.0
    cx = x + w / 2.0
    cy = y + h / 2.0
    return (
        round(clamp(cx / width * 100.0, 0.0, 100.0), 2),
        round(clamp(cy / height * 100.0, 0.0, 100.0), 2),
        round(clamp(w / width * 100.0, 0.0, 100.0), 2),
        round(clamp(h / height * 100.0, 0.0, 100.0), 2),
    )
