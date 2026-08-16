"""vision/engine.py -- Hybrid Vision Engine.

Two backends:
  - Template Matching (fast, for buttons/icons)
  - OCR (slower, for text labels like buff names, HP, coins)

Both work on PIL.Image screenshots and use the existing
emulator/coords.py scale_rect() for ROI extraction.
"""
import os
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from emulator.coords import scale_rect


class VisionEngine:
    """Stateless-ish engine: takes screenshot + point config, returns result."""

    def __init__(self, template_dir=None):
        if template_dir is None:
            template_dir = str(Path(__file__).parent / 'templates')
        self.template_dir = template_dir
        os.makedirs(self.template_dir, exist_ok=True)

    # ── ROI Extraction ──────────────────────────────────
    def extract_roi(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                    view_width, view_height):
        """Cut ROI from screenshot using percent-based rect.

        Returns:
            numpy array (BGR) of the cropped ROI, or None
        """
        rx, ry, rw, rh = scale_rect(
            view_width, view_height, x_pct, y_pct, w_pct, h_pct)

        img_w, img_h = screenshot.size
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

    # ── Template Matching ───────────────────────────────
    def match_template(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                       view_width, view_height, point_name, stage='lobby',
                       threshold=0.8):
        """Find a template image inside the ROI.

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

        safe_name = point_name.replace(' ', '_').replace('/', '_')
        template_path = os.path.join(
            self.template_dir, stage, '%s.png' % safe_name)
        roi_rect = scale_rect(
            view_width, view_height, x_pct, y_pct, w_pct, h_pct)

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

        th, tw = template.shape[:2]
        rh_roi, rw_roi = roi.shape[:2]
        if tw > rw_roi or th > rh_roi:
            scale = min(rw_roi / tw, rh_roi / th) * 0.9
            new_w = int(tw * scale)
            new_h = int(th * scale)
            template = cv2.resize(
                template, (new_w, new_h), interpolation=cv2.INTER_AREA)
            tw, th = new_w, new_h

        result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        elapsed = (time.perf_counter() - t0) * 1000

        if max_val >= threshold:
            match_center_x = roi_rect[0] + max_loc[0] + tw // 2
            match_center_y = roi_rect[1] + max_loc[1] + th // 2
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

    # ── OCR ─────────────────────────────────────────────
    def read_text(self, screenshot, x_pct, y_pct, w_pct, h_pct,
                  view_width, view_height, point_name=None,
                  resize_to=(1280, 720)):
        """Read text from the ROI using pytesseract.

        Returns:
            dict with 'text', 'roi_rect', 'elapsed_ms', or None on error
        """
        t0 = time.perf_counter()

        roi = self.extract_roi(
            screenshot, x_pct, y_pct, w_pct, h_pct,
            view_width, view_height)
        if roi is None:
            return None

        target_w, target_h = resize_to
        roi_pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
        roi_resized = roi_pil.resize((target_w, target_h), Image.LANCZOS)

        roi_gray = roi_resized.convert('L')
        roi_np = np.array(roi_gray)
        _, roi_thresh = cv2.threshold(
            roi_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        try:
            import pytesseract
            text = pytesseract.image_to_string(
                Image.fromarray(roi_thresh),
                config='--psm 7 -c tessedit_char_whitelist='
                       '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                       'abcdefghijklmnopqrstuvwxyz %+-.,/:'
            ).strip()
        except ImportError:
            text = '[pytesseract not installed]'
        except Exception as e:
            text = '[OCR error: %s]' % str(e)

        elapsed = (time.perf_counter() - t0) * 1000
        roi_rect = scale_rect(
            view_width, view_height, x_pct, y_pct, w_pct, h_pct)

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

        return {
            'found': is_found,
            'text': text,
            'roi_rect': roi_rect,
            'elapsed_ms': round(elapsed, 2),
        }

    # ── Unified detect ──────────────────────────────────
    def detect(self, screenshot, x_pct, y_pct, w_pct, h_pct,
               view_width, view_height, point_name, detection_type,
               stage='lobby', threshold=0.8):
        """Unified entry point: dispatches to template or OCR.

        Returns:
            dict with 'type' plus backend-specific keys
        """
        if detection_type == 'template':
            result = self.match_template(
                screenshot, x_pct, y_pct, w_pct, h_pct,
                view_width, view_height, point_name, stage, threshold)
            if result is not None:
                result['type'] = 'template'
            return result

        elif detection_type == 'ocr':
            result = self.read_text(
                screenshot, x_pct, y_pct, w_pct, h_pct,
                view_width, view_height, point_name)
            if result is not None:
                result['type'] = 'ocr'
            return result

        else:
            return {
                'type': 'unknown',
                'error': 'Unknown detection type: %s' % detection_type,
            }
