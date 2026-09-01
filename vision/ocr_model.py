"""vision/ocr_model.py -- OCR runtime pre-loader (English only + disk cache).

โหลด Tesseract OCR แบบครั้งเดียวแล้วจำไว้:
- ครั้งแรกที่เปิดโปรแกรม : ค้นหา tesseract, ตรวจภาษา, อุ่นเครื่อง (warm-up)
  เพื่อโหลดโมเดลเข้า RAM แล้วบันทึกผลลงแคช (ocr_model_cache.json)
- รอบต่อๆ ไป           : อ่านจากแคช ถ้า tesseract ยังอยู่ → จะพร้อมใช้ทันที
  โดยไม่ต้องอุ่นเครื่องซ้ำ → เปิดโปรแกรมเร็วขึ้นมาก

ใช้เฉพาะภาษา อังกฤษ (eng) เท่านั้น สำหรับอ่านข้อความในเกม.

เป็น singleton: ทุกคนเรียกใช้ผ่าน get_ocr_model() (instance เดียว).
"""
import hashlib
import json
import os
import time

# Root ของโปรแกรม (เดียวกับ config.json)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(ROOT_DIR, 'ocr_model_cache.json')

# ภาษาอังกฤษเท่านั้น (อ่านข้อความในเกม)
DEFAULT_LANGUAGES = ('eng',)

# Global singleton instance
ocr_model = None


def get_ocr_model():
    """คืนตัว instance เดียวของ OCR runtime (สร้างครั้งแรกแล้วแคช)."""
    global ocr_model
    if ocr_model is None:
        ocr_model = OcrModel()
    return ocr_model


def _find_tesseract():
    """ค้นหา tesseract.exe — คืน path เต็ม หรือ None."""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd
    except Exception:
        pass

    env = os.environ.get('TESSERACT_CMD', '')
    if env and os.path.isfile(env):
        return env

    for candidate in (
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\Tesseract-OCR\tesseract.exe',
    ):
        if os.path.isfile(candidate):
            return candidate

    # สุดท้ายลองผ่าน PATH
    try:
        import shutil
        found = shutil.which('tesseract')
        if found:
            return found
    except Exception:
        pass
    return None


def _file_fingerprint(path):
    """คืนค่าเปลี่ยนตามขนาด+mtime ของไฟล์ tesseract (ใช้ตรวจสอบแคช)."""
    try:
        st = os.stat(path)
        return '%d-%d' % (st.st_size, int(st.st_mtime))
    except OSError:
        return '?'


class OcrModel:
    """เตรียม Tesseract: ตั้งค่า path, ตรวจภาษา, อุ่นเครื่อง + แคช."""

    def __init__(self, languages=DEFAULT_LANGUAGES):
        self.languages = list(languages)
        self.ready = False
        self.error = None
        self.tesseract_cmd = None
        self.available = []
        self.missing = []
        self._pytesseract = None
        self._warmup_elapsed = 0.0

    @property
    def cache_exists(self):
        return os.path.isfile(CACHE_FILE)

    def _load_cache(self):
        """อ่านแคชถ้ามี และ tesseract ตาม path ยังอยู่จริง."""
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cmd = data.get('tesseract_cmd')
            if cmd and os.path.isfile(cmd):
                self.tesseract_cmd = cmd
                self.available = list(data.get('languages', self.languages))
                self.missing = [lang for lang in self.languages
                                if lang not in self.available]
                return True
        except (OSError, ValueError):
            pass
        return False

    def _save_cache(self):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'tesseract_cmd': self.tesseract_cmd,
                    'languages': self.languages,
                    'version': self._pytesseract.get_tesseract_version().__str__()
                                if self._pytesseract else '',
                    'fingerprint': _file_fingerprint(self.tesseract_cmd or ''),
                    'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                }, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    # ── Load ─────────────────────────────────────────────
    def load(self):
        """โหลด OCR. คืน True ถ้าพร้อมใช้.

        - ถ้ามีแคชและ tesseract ยังอยู่ → ใช้ fast path (ไม่วอร์ม)
        - ถ้าไม่มีแคช → โหลดเต็ม + อุ่นเครื่อง แล้วบันทึกแคช
        รอบหลัง: self.from_cache=True หมายความว่าใช้แคช (เร็ว)
        """
        self.ready = False
        self.from_cache = False

        try:
            import pytesseract
            self._pytesseract = pytesseract
        except ImportError:
            self.error = 'pytesseract not installed'
            return False

        # ---- Fast path: มีแคชใช้ได้ ----
        if self._load_cache():
            try:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                self.from_cache = True
                self.ready = True
                return True
            except Exception:
                pass

        # ---- Full load: ไม่มีแคช / แคชหมดอายุ ----
        cmd = _find_tesseract()
        if not cmd:
            self.error = 'tesseract binary not found'
            return False
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
            self.tesseract_cmd = cmd
        except Exception as e:
            self.error = str(e)
            return False

        try:
            self.available = pytesseract.get_languages(config='')
        except Exception:
            self.available = []
        self.missing = [lang for lang in self.languages
                        if lang not in self.available]

        # Warm-up: อ่าน OCR เล็กๆ ครั้งเดียวให้โมเดลโหลดเข้า RAM
        t0 = time.perf_counter()
        try:
            import cv2
            import numpy as np
            img = np.full((20, 80), 255, dtype=np.uint8)
            pytesseract.image_to_string(
                img, lang='+'.join(self.languages),
                config='--oem 1 --psm 7')
        except Exception:
            pass
        self._warmup_elapsed = (time.perf_counter() - t0) * 1000

        if self.missing:
            # ภาษาที่ต้องการไม่มี — ยังใช้งานได้ถ้ามี eng (อังกฤษ)
            if 'eng' not in self.available and len(self.available) > 0:
                self.languages = [lang for lang in self.languages
                                  if lang in self.available] or ['eng']

        self._save_cache()
        self.ready = True
        self.from_cache = False
        return True

    # ── Usage ────────────────────────────────────────────
    def image_to_string(self, image, config=''):
        """OCR wrapper — ใช้ภาษา eng. คืนข้อความ."""
        if self._pytesseract is None:
            raise RuntimeError('OCR model not loaded')
        return self._pytesseract.image_to_string(
            image, lang='+'.join(self.languages), config=config)
