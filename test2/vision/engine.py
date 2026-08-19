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
import os
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from emulator.coords import scale_rect

# Standard canvas size used as upscale target
_STD_W = 1280
_STD_H = 720


class VisionEngine:
    """Stateless-ish engine: takes screenshot + point config, returns result."""

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
        roi_up = self._upscale_roi(roi, w_pct, h_pct)
        rh_up, rw_up = roi_up.shape[:2]

        # ── Scale template to match upscaled ROI ───────────────────────────
        th_orig, tw_orig = template.shape[:2]
        # Template was saved at 1280×720 standard size — scale it to roi_up
        scale_t = min(rw_up / max(tw_orig, 1), rh_up / max(th_orig, 1))
        new_tw = max(1, int(tw_orig * scale_t))
        new_th = max(1, int(th_orig * scale_t))

        if new_tw != tw_orig or new_th != th_orig:
            interp = cv2.INTER_LANCZOS4 if scale_t >= 1.0 else cv2.INTER_AREA
            template = cv2.resize(template, (new_tw, new_th), interpolation=interp)

        tw, th = new_tw, new_th

        # Ensure template is not larger than ROI (safety guard)
        if tw > rw_up or th > rh_up:
            scale2 = min(rw_up / max(tw, 1), rh_up / max(th, 1)) * 0.95
            template = cv2.resize(template,
                                  (max(1, int(tw * scale2)), max(1, int(th * scale2))),
                                  interpolation=cv2.INTER_AREA)
            th, tw = template.shape[:2]

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
                  resize_to=(1280, 720)):
        """Read text from the ROI using pytesseract.

        ✅ ROI is upscaled with LANCZOS before Otsu thresholding + OCR,
        so text is readable even when the emulator window is very small.

        Returns:
            dict with 'text', 'roi_rect', 'elapsed_ms', or None on error
        """
        t0 = time.perf_counter()

        roi = self.extract_roi(
            screenshot, x_pct, y_pct, w_pct, h_pct,
            view_width, view_height)
        if roi is None:
            return None

        # Upscale ROI: scale so height >= 70 px, clamped 2.5× – 4×
        h, w = roi.shape[:2]
        scale = max(2.5, min(4.0, 70.0 / max(h, 1)))
        new_w = max(int(w * scale), 1)
        new_h = max(int(h * scale), 1)
        roi_resized = cv2.resize(roi, (new_w, new_h),
                                 interpolation=cv2.INTER_LANCZOS4)

        roi_gray = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2GRAY)
        _, roi_thresh = cv2.threshold(
            roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        edge_pixels = np.concatenate(
            [roi_thresh[0, :], roi_thresh[-1, :], roi_thresh[:, 0], roi_thresh[:, -1]])
        if np.mean(edge_pixels) < 127:
            roi_thresh = cv2.bitwise_not(roi_thresh)

        pad = 16
        padded = cv2.copyMakeBorder(
            roi_thresh, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)

        try:
            import pytesseract
            text = pytesseract.image_to_string(
                Image.fromarray(padded),
                config='--psm 7'
            ).strip()
        except ImportError:
            text = '[pytesseract not installed]'
        except Exception as e:
            text = '[OCR error: %s]' % str(e)

        elapsed = (time.perf_counter() - t0) * 1000

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

        return {
            'found': is_found,
            'text': text,
            'roi_rect': roi_rect,
            'elapsed_ms': round(elapsed, 2),
        }

    # ── Unified detect ──────────────────────────────────────────────────────
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
