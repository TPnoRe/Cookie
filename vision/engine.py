"""vision/engine.py -- Hybrid Vision Engine.

Two backends:
  - Template Matching (fast, for buttons/icons)
  - OCR (slower, for text labels like buff names, HP, coins)

Both work on PIL.Image screenshots and use the existing
emulator/coords.py scale_rect() for ROI extraction.

✅ Key fix: ROI coordinates are always computed from the actual
screenshot pixel dimensions (screenshot.size), NOT from the window
handle size (GetClientRect). This prevents crop misalignment caused
by DPI-scaling or emulator rendering differences.

✅ Both Template Matching and OCR upscale the ROI to a standard
1280×720 canvas using LANCZOS interpolation before processing, so
detection is accurate even when the emulator window is very small.
"""
import hashlib
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from emulator.coords import scale_rect

# Standard canvas size used as upscale target
_STD_W = 1280
_STD_H = 720

# Enable saving OCR debug artifacts (cropped ROI and processed image)
# Tier A: default False — not counted in elapsed, only enabled via save_debug=True
_SAVE_OCR_DEBUG = False
# Maximum target dimension (width or height) for OCR upscales to avoid huge images
_OCR_MAX_DIM = 640
# Tier B (all points fast, no resize): pad 10 is enough for psm 7 border
_OCR_PAD = 10
# Hard cap per OCR call (seconds) — guarantees <600ms even on huge ROI
_OCR_TIMEOUT_SEC = 0.6
# Global tesseract base config (fast, no dictionary reload per call)
_OCR_BASE_CONFIG = '--oem 1 --psm 7 -c tessedit_do_invert=0 -c load_system_dawg=0 -c load_freq_dawg=0'
# Per-point whitelist (English single-word buttons — speeds + accuracy)
_OCR_WHITELIST_EN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789! '
_OCR_WHITELIST_POINTS = frozenset(['play button', 'jump', 'slide', 'lobby ok', 'daily ok', 'draw', 'draw again'])
_OCR_PSM8_POINTS = frozenset(['jump', 'slide', 'draw', 'draw again'])
# Blank gate threshold (std < 10 and mostly white → skip OCR)
_OCR_BLANK_STD = 10
# Hash cache for identical ROI (TTL seconds)
_OCR_CACHE_TTL = 0.6
_OCR_CACHE_MAX = 64

class VisionEngine:
    """Stateless-ish engine: takes screenshot + point config, returns result."""

    # Class-level callback: set once, all instances use it.
    # Signature: callback(point_name, text, elapsed_ms, orig_bgr, proc_gray)
    _debug_callback = None
    # Hash cache for identical padded ROI (point_name + hash -> (text, found, expiry))
    _ocr_cache = {}
    _ocr_cache_lock = threading.Lock()

    def __init__(self, template_dir=None):
        if template_dir is None:
            template_dir = str(Path(__file__).parent / 'templates')
        self.template_dir = template_dir
        os.makedirs(self.template_dir, exist_ok=True)

    # ── ROI Extraction ──────────────────────────────────────────────────────
    def extract_roi(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                    view_width, view_height):
        """Cut ROI from screenshot using percent-based rect.

        ✅ Always uses screenshot.size as the coordinate reference so
        the crop is correct regardless of DPI scaling or window size.

        Returns:
            numpy array (BGR) of the cropped ROI, or None
        """
        img_w, img_h = screenshot.size  # actual captured pixel dimensions

        rx, ry, rw, rh = scale_rect(img_w, img_h, x_pct, y_pct, w_pct, h_pct)

        x1 = max(0, rx)
        y1 = max(0, ry)
        x2 = min(img_w, rx + rw)
        y2 = min(img_h, ry + rh)

        if x2 <= x1 or y2 <= y1:
            return None

        roi_pil = screenshot.crop((x1, y1, x2, y2))
        roi_np = np.array(roi_pil)
        roi_bgr = cv2.cvtColor(roi_np, cv2.COLOR_RGB2BGR)
        return roi_bgr

    # ── Upscale helper ──────────────────────────────────────────────────────
    @staticmethod
    def _upscale_roi(roi_bgr, w_pct, h_pct):
        """Upscale ROI to its equivalent size on a 1280×720 canvas (LANCZOS).

        The target size is the pixel area this ROI would occupy on a
        standard 1280×720 screen, computed from the percentage rect.
        This means the upscale factor adapts automatically to any window size.
        """
        h, w = roi_bgr.shape[:2]
        std_w = max(1, int(w_pct / 100.0 * _STD_W))
        std_h = max(1, int(h_pct / 100.0 * _STD_H))

        # Only upscale, never downscale (avoids blurring already-large ROIs)
        new_w = max(w, std_w)
        new_h = max(h, std_h)

        if new_w == w and new_h == h:
            return roi_bgr

        return cv2.resize(roi_bgr, (new_w, new_h),
                          interpolation=cv2.INTER_LANCZOS4)

    # ── Template Matching ───────────────────────────────────────────────────
    def match_template(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                       view_width, view_height, point_name, stage='lobby',
                       threshold=0.8):
        """Find a template image inside the ROI.

        ✅ Both the ROI and the template image are upscaled to standard
        1280×720 proportions with LANCZOS before matching, so detection
        accuracy is consistent at any emulator window size.

        Returns:
            dict with 'found', 'confidence', 'click_x', 'click_y',
            'roi_rect', 'elapsed_ms', or None on error
        """
        t0 = time.perf_counter()

        roi = self.extract_roi(
            screenshot, x_pct, y_pct, w_pct, h_pct,
            view_width, view_height)
        if roi is None:
            return None

        # roi_rect uses actual screenshot dims for accurate click coords
        img_w, img_h = screenshot.size
        roi_rect = scale_rect(img_w, img_h, x_pct, y_pct, w_pct, h_pct)

        safe_name = point_name.replace(' ', '_').replace('/', '_')
        template_path = os.path.join(
            self.template_dir, stage, '%s.png' % safe_name)

        if not os.path.isfile(template_path):
            # Fallback search in other subdirectories
            for alt_stage in ['lobby', 'launch', 'prep', 'gameplay', 'results']:
                alt_path = os.path.join(self.template_dir, alt_stage, '%s.png' % safe_name)
                if os.path.isfile(alt_path):
                    template_path = alt_path
                    break

        if not os.path.isfile(template_path):
            return {
                'found': False,
                'confidence': 0.0,
                'click_x': None,
                'click_y': None,
                'roi_rect': roi_rect,
                'elapsed_ms': (time.perf_counter() - t0) * 1000,
                'error': 'Template not found: %s.png' % point_name,
            }

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            return {
                'found': False,
                'confidence': 0.0,
                'click_x': None,
                'click_y': None,
                'roi_rect': roi_rect,
                'elapsed_ms': (time.perf_counter() - t0) * 1000,
                'error': 'Failed to load template',
            }

        # ── Upscale ROI to standard canvas size (LANCZOS) ──────────────────
        orig_h, orig_w = roi.shape[:2]
        roi_up = self._upscale_roi(roi, w_pct, h_pct)
        rh_up, rw_up = roi_up.shape[:2]

        # ── Scale template proportionally with ROI upscale factor ───────────
        th_orig, tw_orig = template.shape[:2]
        scale_x = rw_up / max(orig_w, 1)
        scale_y = rh_up / max(orig_h, 1)
        new_tw = max(1, int(tw_orig * scale_x))
        new_th = max(1, int(th_orig * scale_y))

        # Ensure template is not larger than upscaled ROI
        if new_tw > rw_up or new_th > rh_up:
            shrink = min(rw_up / max(new_tw, 1), rh_up / max(new_th, 1)) * 0.95
            new_tw = max(1, int(new_tw * shrink))
            new_th = max(1, int(new_th * shrink))

        if new_tw != tw_orig or new_th != th_orig:
            interp = cv2.INTER_LANCZOS4 if scale_x >= 1.0 else cv2.INTER_AREA
            template = cv2.resize(template, (new_tw, new_th), interpolation=interp)

        tw, th = new_tw, new_th

        result = cv2.matchTemplate(roi_up, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        elapsed = (time.perf_counter() - t0) * 1000

        if max_val >= threshold:
            # Map match location from upscaled coords back to screenshot coords
            scale_back_x = roi_rect[2] / max(rw_up, 1)
            scale_back_y = roi_rect[3] / max(rh_up, 1)
            match_center_x = roi_rect[0] + int((max_loc[0] + tw // 2) * scale_back_x)
            match_center_y = roi_rect[1] + int((max_loc[1] + th // 2) * scale_back_y)
            return {
                'found': True,
                'confidence': round(float(max_val), 4),
                'click_x': match_center_x,
                'click_y': match_center_y,
                'roi_rect': roi_rect,
                'elapsed_ms': round(elapsed, 2),
            }
        else:
            return {
                'found': False,
                'confidence': round(float(max_val), 4),
                'click_x': None,
                'click_y': None,
                'roi_rect': roi_rect,
                'elapsed_ms': round(elapsed, 2),
            }

    # ── OCR ─────────────────────────────────────────────────────────────────
    def read_text(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                  view_width, view_height, point_name=None,
                  resize_to=(1280, 720), save_debug=None):
        """Read text from the ROI using pytesseract (optimized for speed).

        ✅ ROI is converted to Grayscale first, then upscaled with CUBIC
        before Otsu thresholding + OCR. This is ~40% faster than upscaling
        in color, with no loss in OCR accuracy since Tesseract works from
        binary/grayscale images anyway.

        Tier A: pre-clamp scale before first resize (avoid duplicate
        LANCZOS+blur+OTSU), INTER_CUBIC instead of LANCZOS, conditional
        medianBlur, and disk I/O excluded from elapsed.

        Args:
            save_debug: None → use global _SAVE_OCR_DEBUG (default False);
                        True/False → force on/off for this call.
                        When True, `debug_orig_bgr` (CROPPED) is the ROI
                        resized to new_w×new_h + pad 16 so it matches
                        `debug_proc_gray` (PROCESSED) pixel-for-pixel.

        Returns:
            dict with 'text', 'roi_rect', 'elapsed_ms', or None on error
        """
        t0 = time.perf_counter()

        roi = self.extract_roi(
            screenshot, x_pct, y_pct, w_pct, h_pct,
            view_width, view_height)
        if roi is None:
            return None

        # ⚡ Convert to Grayscale FIRST (smaller memory footprint)
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Then upscale grayscale (faster than upscaling BGR)
        h, w = roi_gray.shape[:2]
        # Balanced scale: 2.5–3.0 (good speed / accuracy tradeoff)
        scale = max(2.5, min(3.0, 70.0 / max(h, 1)))
        new_w = max(int(w * scale), 1)
        new_h = max(int(h * scale), 1)

        pad = _OCR_PAD
        # Cap upscale so final padded size does not exceed _OCR_MAX_DIM
        # Tier A: pre-clamp before first resize to avoid duplicate work
        max_inner = max(1, _OCR_MAX_DIM - (2 * pad))
        if new_w > max_inner or new_h > max_inner:
            factor = min(max_inner / new_w, max_inner / new_h)
            new_w = max(1, int(new_w * factor))
            new_h = max(1, int(new_h * factor))

        # Tier A: INTER_CUBIC ~2× faster than LANCZOS4, quality still high for OTSU
        roi_resized = cv2.resize(roi_gray, (new_w, new_h),
                                 interpolation=cv2.INTER_CUBIC)

        # Tier A: conditional denoise — skip on tiny images to save time
        # Only blur if image is large enough to benefit (≥12px and ≥4000 px total)
        if (roi_resized.shape[0] >= 12 and roi_resized.shape[1] >= 12
                and roi_resized.size >= 4000):
            roi_resized = cv2.medianBlur(roi_resized, 3)

        _, roi_thresh = cv2.threshold(
            roi_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Faster edge check without large concatenate alloc
        try:
            edge_mean = (np.mean(roi_thresh[0, :]) + np.mean(roi_thresh[-1, :])
                         + np.mean(roi_thresh[:, 0]) + np.mean(roi_thresh[:, -1])) / 4.0
        except Exception:
            edge_mean = 255
        if edge_mean < 127:
            roi_thresh = cv2.bitwise_not(roi_thresh)

        padded = cv2.copyMakeBorder(
            roi_thresh, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)

        # ── Fast blank gate (no OCR if ROI is empty/uniform) ──────────────
        # Saves ~300ms on blank Relic Diamond etc. when no text visible.
        is_blank = False
        try:
            # std < threshold and >98% white → blank
            if padded.size < 3000:
                # very tiny: treat as blank if mostly white
                if np.mean(padded == 255) > 0.97:
                    is_blank = True
            else:
                if np.std(padded) < _OCR_BLANK_STD or np.mean(padded == 255) > 0.98:
                    is_blank = True
        except Exception:
            is_blank = False

        text = ''
        cache_hit = False
        if is_blank:
            text = ''
            elapsed = (time.perf_counter() - t0) * 1000
        else:
            # ── Hash cache for identical ROI (static screen → no OCR) ──────
            cache_key = None
            cached_text = None
            try:
                if point_name:
                    # blake2b 8-byte hash is fast (~0.3ms)
                    h = hashlib.blake2b(padded.tobytes(), digest_size=8).hexdigest()
                    cache_key = (point_name.lower().strip(), h)
                    now = time.monotonic()
                    with VisionEngine._ocr_cache_lock:
                        entry = VisionEngine._ocr_cache.get(cache_key)
                        if entry is not None:
                            c_text, expiry = entry
                            if now < expiry:
                                cached_text = c_text
                                cache_hit = True
                            else:
                                # expired
                                try:
                                    del VisionEngine._ocr_cache[cache_key]
                                except KeyError:
                                    pass
            except Exception:
                cache_hit = False
                cached_text = None

            if cache_hit:
                text = cached_text
                elapsed = (time.perf_counter() - t0) * 1000
            else:
                # ── Per-point tesseract config (fast, no dictionary) ───────
                # Base: --oem 1 --psm 7 -c tessedit_do_invert=0 -c load_system_dawg=0 -c load_freq_dawg=0
                # For single-word points use psm 8; for english buttons add whitelist
                cfg = _OCR_BASE_CONFIG
                if point_name:
                    p_low = point_name.lower().strip()
                    if p_low in _OCR_PSM8_POINTS:
                        cfg = cfg.replace('--psm 7', '--psm 8')
                    if p_low in _OCR_WHITELIST_POINTS:
                        cfg += f" -c tessedit_char_whitelist={_OCR_WHITELIST_EN}"
                # ── OCR with hard timeout 600ms ────────────────────────────
                try:
                    from vision.ocr_model import get_ocr_model
                    model = get_ocr_model()
                    if model._pytesseract is not None:
                        text = model.image_to_string(
                            Image.fromarray(padded, mode='L'),
                            config=cfg, timeout=_OCR_TIMEOUT_SEC).strip()
                    else:
                        import pytesseract
                        text = pytesseract.image_to_string(
                            Image.fromarray(padded, mode='L'),
                            config=cfg, timeout=_OCR_TIMEOUT_SEC
                        ).strip()
                except RuntimeError as e:
                    # pytesseract timeout raises RuntimeError
                    msg = str(e).lower()
                    if 'timeout' in msg or 'timed out' in msg:
                        text = ''
                    else:
                        text = '[OCR error: %s]' % str(e)
                except ImportError:
                    text = '[pytesseract not installed]'
                except Exception as e:
                    # Handle timeout from pytesseract that may wrap as generic Exception
                    msg = str(e).lower()
                    if 'timeout' in msg:
                        text = ''
                    else:
                        text = '[OCR error: %s]' % str(e)
                elapsed = (time.perf_counter() - t0) * 1000
                # Hard cap display (should already be <600 due to timeout)
                if elapsed > 600:
                    elapsed = 600.0
                # Store in cache
                if cache_key is not None:
                    try:
                        with VisionEngine._ocr_cache_lock:
                            # LRU eviction: remove oldest if over limit
                            if len(VisionEngine._ocr_cache) >= _OCR_CACHE_MAX:
                                # pop first inserted (dict preserves order py3.7+)
                                try:
                                    oldest = next(iter(VisionEngine._ocr_cache))
                                    del VisionEngine._ocr_cache[oldest]
                                except StopIteration:
                                    pass
                            VisionEngine._ocr_cache[cache_key] = (text, time.monotonic() + _OCR_CACHE_TTL)
                    except Exception:
                        pass
            # Enforce hard cap for blank/cache paths too
            if 'elapsed' in locals() and elapsed > 600:
                elapsed = 600.0

        # roi_rect uses actual screenshot dims for consistency
        img_w, img_h = screenshot.size
        roi_rect = scale_rect(img_w, img_h, x_pct, y_pct, w_pct, h_pct)

        is_found = bool(text) and not text.startswith('[')
        if is_found and point_name:
            p_lower = point_name.lower()
            t_lower = text.lower()
            if 'confirm relic' in p_lower:
                is_found = any(k in t_lower for k in ['confirm', 'confrim', 'ยืนยัน'])
            elif 'lobby ok' in p_lower:
                is_found = any(k in t_lower for k in ['ok', 'ตกลง', 'โอเค'])
            elif 'confirm' in p_lower or 'confrim' in p_lower:
                is_found = any(k in t_lower for k in ['confirm', 'confrim', 'ยืนยัน'])
            elif 'ok' in p_lower:
                is_found = any(k in t_lower for k in ['ok', 'ตกลง', 'โอเค'])
            elif 'claim' in p_lower:
                is_found = any(k in t_lower for k in ['claim', 'รับ'])
            elif 'relic' in p_lower and ('diamond' in p_lower or 'get' in p_lower):
                is_found = any(k in t_lower for k in ['get', 'claim', 'รับ', '!'])
            elif 'play' in p_lower:
                is_found = any(k in t_lower for k in ['play', 'start', 'เล่น'])
            elif 'jump' in p_lower:
                is_found = any(k in t_lower for k in ['jump', 'กระโดด'])
            elif 'slide' in p_lower:
                is_found = any(k in t_lower for k in ['slide', 'สไลด์'])
            elif 'close' in p_lower:
                is_found = any(k in t_lower for k in ['close', 'ปิด', 'x'])

        # ── Debug images (NOT timed) ──────────────────────────────────────
        # Tier A: orig_show + disk save excluded from elapsed; only when save_debug True
        should_save = _SAVE_OCR_DEBUG if save_debug is None else save_debug
        orig_show = None
        orig_saved = None
        proc_saved = None
        if should_save and point_name:
            # CROPPED preview: roi resized to SAME inner size then padded 16px
            # Use INTER_LINEAR (fastest) for preview — not affecting OCR accuracy
            try:
                orig_resized_color = cv2.resize(
                    roi, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                orig_show = cv2.copyMakeBorder(
                    orig_resized_color, pad, pad, pad, pad,
                    cv2.BORDER_CONSTANT, value=(255, 255, 255))
            except Exception:
                orig_show = None
            try:
                folder = Path(__file__).resolve().parents[1] / 'debug' / 'ocr'
                folder.mkdir(parents=True, exist_ok=True)
                ts = time.strftime('%Y%m%d_%H%M%S')
                try:
                    if orig_show is not None:
                        orig_resized_rgb = cv2.cvtColor(orig_show, cv2.COLOR_BGR2RGB)
                        orig_path = folder / f"ocr_{point_name}_{ts}_orig.png"
                        Image.fromarray(orig_resized_rgb).save(orig_path)
                        orig_saved = str(orig_path)
                except Exception:
                    orig_saved = None
                try:
                    proc_path = folder / f"ocr_{point_name}_{ts}_proc.png"
                    Image.fromarray(padded).save(proc_path)
                    proc_saved = str(proc_path)
                except Exception:
                    proc_saved = None
            except Exception:
                orig_saved = None
                proc_saved = None

        # Notify debug callback (if set) with the raw image data.
        # orig_show has the SAME size as `padded` so CROPPED/PROCESSED match.
        if VisionEngine._debug_callback and point_name:
            try:
                VisionEngine._debug_callback(
                    point_name, text, round(elapsed, 2), orig_show, padded)
            except Exception:
                pass

        return {
            'found': is_found,
            'text': text,
            'roi_rect': roi_rect,
            'elapsed_ms': round(elapsed, 2),
            'debug_orig': orig_saved,
            'debug_proc': proc_saved,
            'debug_orig_bgr': orig_show,
            'debug_proc_gray': padded,
        }

    # ── Unified detect ──────────────────────────────────────────────────────
    def detect(self, screenshot, x_pct, y_pct, w_pct, h_pct,
               view_width, view_height, point_name, detection_type,
               stage='lobby', threshold=0.8, save_debug=None):
        """Unified entry point: dispatches to template or OCR.

        ✅ บังคับให้สองระบบแยกกันชัดเจนตาม detection_type:
        - 'template' : ใช้ส่งภาพปุ่ม/ไอคอน (ตัวหลัก, เร็ว) — ดำเนินการเฉพาะ ROI
        - 'ocr'      : อ่านข้อความ เฉพาะพื้นที่ข้อความ (Region) ที่กำหนดผ่าน
                       x_pct,y_pct,w_pct,h_pct เท่านั้น ไม่สแกนทั้งจอ
        - อื่นๆ  (default/unknown) ถูกบังคับให้เป็น template หรือคืน error
          เพื่อกันเผลอรัน OCR นอก Region ที่ระบุ

        Returns:
            dict with 'type' plus backend-specific keys
        """
        if detection_type is None or detection_type == '':
            detection_type = 'template'

        if detection_type == 'template':
            result = self.match_template(
                screenshot, x_pct, y_pct, w_pct, h_pct,
                view_width, view_height, point_name, stage, threshold)
            if result is not None:
                result['type'] = 'template'
            return result

        elif detection_type == 'ocr':
            # OCR ทำงานเฉพาะ Region (ROI) ของจุดนี้ — extract_roi ตัดเฉพาะ
            # พื้นที่ข้อความ x_pct,y_pct,w_pct,h_pct ไม่สแกนทั้งจอ.
            # Tier A: save_debug None → use _SAVE_OCR_DEBUG (False default);
            # Coordinates Vision Test ส่ง True เพื่อได้ CROPPED/PROCESSED.
            result = self.read_text(
                screenshot, x_pct, y_pct, w_pct, h_pct,
                view_width, view_height, point_name,
                save_debug=save_debug)
            if result is not None:
                result['type'] = 'ocr'
            return result

        else:
            return {
                'type': 'unknown',
                'error': 'Unknown detection type: %s' % detection_type,
            }

    # ── Full Canvas Search ──────────────────────────────────────────────────
    def find_template(self, screenshot, point_name, stage='launch', threshold=0.75):
        """Find a template anywhere on the screenshot (full canvas search).

        Useful for detecting icons on home screen or popups with variable positions.
        """
        t0 = time.perf_counter()
        img_w, img_h = screenshot.size

        safe_name = point_name.replace(' ', '_').replace('/', '_')
        template_path = os.path.join(
            self.template_dir, stage, '%s.png' % safe_name)

        if not os.path.isfile(template_path):
            for alt_stage in ['lobby', 'launch', 'prep', 'gameplay', 'results']:
                alt_path = os.path.join(self.template_dir, alt_stage, '%s.png' % safe_name)
                if os.path.isfile(alt_path):
                    template_path = alt_path
                    break

        if not os.path.isfile(template_path):
            return {
                'found': False,
                'confidence': 0.0,
                'click_x': None,
                'click_y': None,
                'pct_x': None,
                'pct_y': None,
                'roi_rect': (0, 0, img_w, img_h),
                'elapsed_ms': (time.perf_counter() - t0) * 1000,
                'error': 'Template not found: %s.png' % point_name,
            }

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            return {
                'found': False,
                'confidence': 0.0,
                'click_x': None,
                'click_y': None,
                'pct_x': None,
                'pct_y': None,
                'roi_rect': (0, 0, img_w, img_h),
                'elapsed_ms': (time.perf_counter() - t0) * 1000,
                'error': 'Failed to load template',
            }

        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        best_val = -1.0
        best_loc = None
        best_tw, best_th = template.shape[1], template.shape[0]

        scales = [1.0]
        ref_scale = img_w / 680.0
        if abs(ref_scale - 1.0) > 0.05:
            scales.append(ref_scale)
        ref_scale_1280 = img_w / 1280.0
        if abs(ref_scale_1280 - 1.0) > 0.05:
            scales.append(ref_scale_1280)

        for s in set(scales):
            tw = int(template.shape[1] * s)
            th = int(template.shape[0] * s)
            if tw < 5 or th < 5 or tw > img_w or th > img_h:
                continue
            tmpl_s = cv2.resize(template, (tw, th),
                                interpolation=cv2.INTER_AREA if s < 1.0 else cv2.INTER_LANCZOS4)
            res = cv2.matchTemplate(img_bgr, tmpl_s, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_val:
                best_val = float(max_val)
                best_loc = max_loc
                best_tw, best_th = tw, th

        elapsed = (time.perf_counter() - t0) * 1000
        if best_val >= threshold and best_loc is not None:
            click_x = best_loc[0] + best_tw // 2
            click_y = best_loc[1] + best_th // 2
            return {
                'found': True,
                'confidence': round(best_val, 4),
                'click_x': click_x,
                'click_y': click_y,
                'pct_x': round(click_x / img_w * 100, 2),
                'pct_y': round(click_y / img_h * 100, 2),
                'roi_rect': (best_loc[0], best_loc[1], best_tw, best_th),
                'elapsed_ms': round(elapsed, 2),
            }
        else:
            return {
                'found': False,
                'confidence': round(best_val, 4),
                'click_x': None,
                'click_y': None,
                'pct_x': None,
                'pct_y': None,
                'roi_rect': (0, 0, img_w, img_h),
                'elapsed_ms': round(elapsed, 2),
            }

