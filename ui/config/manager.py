"""Config manager — โหลด/บันทึก config.json (ตั้งค่า + พิกัด) ไว้ที่โฟลเดอร์เดียวกับ main.py."""

import copy
import json
import os

from ui.config.defaults import DEFAULT_CONFIG

CONFIG_FILENAME = 'config.json'
# ui/config/manager.py -> root = ../../ (เดียวกับ main.py)
CONFIG_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_BOOL_SETTINGS = {'fast_start', 'cookie_relay', 'relic_check', 'random_boost'}
_NUMBER_LIMITS = {
    'jump_interval': (0.10, 10.0),
    'click_delay_min': (0.0, 5.0),
    'click_delay_max': (0.0, 5.0),
    'click_hold': (0.0, 5.0),
    'click_jitter_pct': (0.0, 10.0),
    'click_jitter_px': (0.0, 100.0),
    'fast_start_delay': (0.0, 10.0),
}


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


def _normalize_settings(settings):
    """Keep corrupted/manual config values from breaking the bot loop."""
    for key in _BOOL_SETTINGS:
        value = settings.get(key)
        if isinstance(value, str):
            settings[key] = value.strip().lower() in ('1', 'true', 'yes', 'on')
        elif value is not None:
            settings[key] = bool(value)

    for key, (minimum, maximum) in _NUMBER_LIMITS.items():
        default = DEFAULT_CONFIG['settings'][key]
        try:
            value = float(settings.get(key, default))
        except (TypeError, ValueError):
            value = float(default)
        settings[key] = max(minimum, min(maximum, value))

    # A reversed delay range is valid input but should behave predictably.
    if settings['click_delay_min'] > settings['click_delay_max']:
        settings['click_delay_min'], settings['click_delay_max'] = (
            settings['click_delay_max'], settings['click_delay_min'])


class Config:
    """จัดการ config ทั้งหมดของโปรแกรม (โหลดครั้งเดียว, บันทึกเมื่อ save)."""

    def __init__(self, path=None):
        self.path = path or os.path.join(CONFIG_DIR, CONFIG_FILENAME)
        self.data = _deep_merge(DEFAULT_CONFIG, {})
        self.last_error = None
        self.load()

    # ── Load / Save ──────────────────────────────────────
    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            self.data = _deep_merge(DEFAULT_CONFIG, saved)
            _normalize_settings(self.settings)
            self.last_error = None
        except (OSError, ValueError) as exc:
            self.last_error = 'Cannot load config: %s' % exc

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
        _normalize_settings(self.settings)
