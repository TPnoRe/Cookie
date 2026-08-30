"""core/dependencies.py -- ตรวจสอบ + ติดตั้ง dependency ก่อนเปิดหน้าต่างหลัก.

ใช้ importlib (ไม่ import จริง) เพื่อให้เช็คซ้ำหลังติดตั้งได้ทันที
โดยไม่ต้องรีสตาร์ทโปรแกรม และ main.py ไม่ต้อง import ui/emulator
ตั้งแต่บนสุด (กัน crash ถ้า pywin32 ขาด).

สถานะ dependency แบ่งเป็น:
- critical : ถ้าขาดโปรแกรมเปิด/รันไม่ได้ (pywin32)
- optional : ถ้าขาดบางฟีเจอร์ใช้ไม่ได้ แต่เปิดโปรแกรมได้ (pytesseract/Tesseract)
"""
import importlib
import shutil
import subprocess
import sys


def _can_import(module_name):
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _tesseract_binary_ok():
    if not _can_import('pytesseract'):
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _winget_available():
    return shutil.which('winget') is not None


def check_dependencies():
    """เช็ค dependency ทั้งหมด → list dict {key, label, pip, critical, ok, detail}."""
    checks = [
        {
            'key': 'pywin32',
            'label': 'pywin32 (Win32 API)',
            'pip': 'pywin32',
            'critical': True,
            'ok': _can_import('win32gui'),
            'detail': 'ใช้สำหรับ Background Click / จับหน้าจอ Emulator',
        },
        {
            'key': 'pytesseract',
            'label': 'pytesseract (OCR wrapper)',
            'pip': 'pytesseract',
            'critical': False,
            'ok': _can_import('pytesseract'),
            'detail': 'ใช้สำหรับอ่านข้อความ (Jump/Slide/Buff)',
        },
        {
            'key': 'tesseract',
            'label': 'Tesseract OCR (โปรแกรม)',
            'pip': None,
            'critical': False,
            'ok': _tesseract_binary_ok(),
            'detail': 'ติดตั้งแยกจาก pip — ใช้ winget หรือลงเอง',
        },
        {
            'key': 'opencv',
            'label': 'OpenCV (cv2)',
            'pip': 'opencv-python',
            'critical': True,
            'ok': _can_import('cv2'),
            'detail': 'ใช้สำหรับ Template Matching',
        },
        {
            'key': 'pillow',
            'label': 'Pillow (PIL)',
            'pip': 'Pillow',
            'critical': True,
            'ok': _can_import('PIL'),
            'detail': 'ใช้จัดการภาพ screenshot',
        },
        {
            'key': 'numpy',
            'label': 'NumPy',
            'pip': 'numpy',
            'critical': True,
            'ok': _can_import('numpy'),
            'detail': 'ใช้คำนวณภาพ',
        },
    ]
    return checks


def missing_pip_packages(checks):
    """ชื่อ pip package ที่ขาด (เรียงตามลำดับเช็ค)."""
    return [c['pip'] for c in checks if not c['ok'] and c['pip']]


def missing_tesseract(checks):
    for c in checks:
        if c['key'] == 'tesseract' and not c['ok']:
            return True
    return False


def critical_missing(checks):
    """มี dependency ระดับ critical ที่ขาดหรือไม่."""
    return any(not c['ok'] for c in checks if c['critical'])


def run_pip_install(packages, on_line=None):
    """รัน pip install (stream output). คืน True ถ้าสำเร็จ."""
    if not packages:
        return True
    cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade'] + packages
    return _run_streaming(cmd, on_line)


def run_winget_tesseract(on_line=None):
    """รัน winget ติดตั้ง Tesseract OCR. คืน True ถ้าสำเร็จ."""
    if not _winget_available():
        return False
    cmd = ['winget', 'install', '--id', 'UB-Mannheim.TesseractOCR', '-e',
           '--accept-package-agreements', '--accept-source-agreements']
    return _run_streaming(cmd, on_line)


def _run_streaming(cmd, on_line=None):
    """รัน subprocess และส่งแต่ละบรรทัดออกทาง callback (สำหรับ UI)."""
    try:
        # Prevent pip/winget from flashing a console window. Their output is
        # still streamed into the splash UI through stdout.
        startupinfo = None
        creationflags = 0
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8', errors='replace',
            startupinfo=startupinfo, creationflags=creationflags)
        for line in proc.stdout:
            text = line.rstrip()
            if text and on_line:
                on_line(text)
        proc.wait()
        return proc.returncode == 0
    except OSError as e:
        if on_line:
            on_line('[ติดตั้งไม่สำเร็จ: %s]' % e)
        return False
