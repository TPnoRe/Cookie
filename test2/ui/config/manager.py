"""Config manager — โหลด/บันทึก config.json (ตั้งค่า + พิกัด) ไว้ที่โฟลเดอร์เดียวกับ main.py."""

import copy
import json
import os

from ui.config.defaults import DEFAULT_CONFIG

CONFIG_FILENAME = 'config.json'
# ui/config/manager.py -> root = ../../ (เดียวกับ main.py)
CONFIG_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _deep_merge(base, overlay):
    """Merge dict ลึก: ค่าที่ไม่มีใน overlay ใช้ของ base, อันใหม่ก็ใส่เข้าไป."""
    result = copy.deepcopy(base)
    if not isinstance(overlay, dict):
        return result
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """จัดการ config ทั้งหมดของโปรแกรม (โหลดครั้งเดียว, บันทึกเมื่อ save)."""

    def __init__(self, path=None):
        self.path = path or os.path.join(CONFIG_DIR, CONFIG_FILENAME)
        self.data = _deep_merge(DEFAULT_CONFIG, {})
        self.load()

    # ── Load / Save ──────────────────────────────────────
    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            self.data = _deep_merge(DEFAULT_CONFIG, saved)
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False

    # ── Accessors ────────────────────────────────────────
    @property
    def settings(self):
        return self.data['settings']

    @property
    def coordinates(self):
        return self.data['coordinates']

    def get_coords(self, stage):
        stage_data = self.coordinates.setdefault(stage, [])
        return [list(p) for p in stage_data]

    def get_all_coords(self):
        return {stage: self.get_coords(stage) for stage in ['lobby', 'prep', 'gameplay', 'results']}

    def set_coords(self, stage, points):
        self.coordinates[stage] = [list(p) for p in points]

    def get_detection(self, point_name, default='template'):
        detection = self.data.setdefault('detection', {})
        return detection.get(point_name, default)

    def set_detection(self, point_name, detection_type):
        detection = self.data.setdefault('detection', {})
        if detection_type in ('template', 'ocr'):
            detection[point_name] = detection_type

    def get_settings(self):
        return copy.deepcopy(self.settings)

    def update_settings(self, data):
        self.settings.update(copy.deepcopy(data))
