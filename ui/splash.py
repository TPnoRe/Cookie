"""ui/splash.py -- หน้าต่างโหลด + ตรวจ/ติดตั้ง Dependency อัตโนมัติ.

ลำดับอัตโนมัติ:
1. ตรวจสอบส่วนประกอบ (progress ~5%)
2. ติดตั้ง pip packages ที่ขาด (ถ้ามี) — progress 15→68
3. ติดตั้ง Tesseract OCR ผ่าน winget (ถ้าขาด + มี winget) — progress 70→90
4. เช็คซ้ำ → progress 100% → เปิดหน้าต่างหลักเอง

ถ้าติดตั้งไม่สำเร็จ: หยุด + โชว์ปุ่มลองใหม่ (ไม่เปิดโปรแกรมต่อ)

สำคัญ: ไฟล์นี้ต้องไม่ import ตัว win32 / emulator / ui.app
เพื่อให้ splash ขึ้นได้แม้ pywin32 จะยังไม่ได้ติดตั้ง.
"""
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
)

import os

from core.dependencies import (
    check_dependencies, critical_missing, missing_pip_packages,
    missing_tesseract, run_pip_install, run_winget_tesseract, _winget_available,
)
from ui import theme


class _InstallWorker(QThread):
    """รัน pip / winget ในเธรดแยก ส่ง output กลับทีละบรรทัด."""

    line = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, task, packages):
        super().__init__()
        self._task = task
        self._packages = packages

    def run(self):
        if self._task == 'pip':
            ok = run_pip_install(self._packages, on_line=self._emit_line)
        elif self._task == 'winget':
            ok = run_winget_tesseract(on_line=self._emit_line)
        elif self._task == 'ocr_model':
            # โหลด + อุ่นเครื่อง OCR ล่วงหน้า (ทำใน background thread)
            try:
                from vision.ocr_model import get_ocr_model
                model = get_ocr_model()
                ok = model.load()
            except Exception as e:
                self._emit_line('[OCR load error: %s]' % e)
                ok = False
        else:
            ok = False
        self.done.emit(ok)

    def _emit_line(self, text):
        self.line.emit(text)


class SplashWindow(QDialog):
    """หน้าต่าง splash — โหลด/ติดตั้งอัตโนมัติ แล้วเปิดโปรแกรมเอง."""

    continue_signal = pyqtSignal()
    cancel_signal = pyqtSignal()

    def __init__(self, checks=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Cookie Run Classic Bot')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Dialog)
        self.setMinimumSize(500, 560)
        self._checks = checks if checks is not None else check_dependencies()
        self._worker = None
        self._progress_timer = None
        self._anim_cap = 0
        self._flow_started = False
        self._proceed = False

        self.setStyleSheet(theme.app_style() + SPLASH_QSS)
        self._build()
        self._center()
        self._refresh()

    # ── UI ───────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)

        # header
        header = QFrame()
        header.setObjectName('splashHeader')
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel('\u2B21 Cookie Run Bot — Mech Edition v2.1')
        title.setObjectName('splashTitle')
        title_col.addWidget(title)
        subtitle = QLabel('กำลังเชื่อมต่อระบบ Mecha Subsystems & Calibrating...')
        subtitle.setObjectName('splashSub')
        title_col.addWidget(subtitle)
        hl.addLayout(title_col)
        hl.addStretch(1)

        close_btn = QPushButton('\u2715')
        close_btn.setObjectName('splashClose')
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._on_cancel)
        hl.addWidget(close_btn)
        root.addWidget(header)

        # status + progress
        self._status = QLabel('กำลังตรวจสอบส่วนประกอบ...')
        self._status.setObjectName('splashStatus')
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        # dependency list
        card = QFrame()
        card.setObjectName('card')
        gl = QGridLayout(card)
        gl.setContentsMargins(14, 12, 14, 12)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(6)
        self._status_labels = {}
        for i, c in enumerate(self._checks):
            name = QLabel(c['label'])
            name.setObjectName('depName')
            gl.addWidget(name, i, 0)
            status = QLabel()
            status.setObjectName('depStatus')
            status.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
            gl.addWidget(status, i, 1)
            self._status_labels[c['key']] = (name, status)
        gl.setColumnStretch(0, 1)
        root.addWidget(card)

        # log (โชว์เมื่อมี output)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setPlaceholderText('(log การติดตั้งจะแสดงที่นี่)')
        self._log.hide()
        root.addWidget(self._log)

        # retry (โชว์เมื่อติดตั้งล้มเหลว)
        self._retry_btn = QPushButton('ลองติดตั้งอีกครั้ง')
        self._retry_btn.setProperty('btn', 'primary')
        self._retry_btn.clicked.connect(self._start_flow)
        self._retry_btn.hide()
        root.addWidget(self._retry_btn)

    def _center(self):
        from PyQt6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move((geo.width() - self.width()) // 2,
                  (geo.height() - self.height()) // 2)

    # ── State ────────────────────────────────────────────
    def _refresh(self):
        self._checks = check_dependencies()
        for c in self._checks:
            pair = self._status_labels.get(c['key'])
            if not pair:
                continue
            _, status = pair
            if c['ok']:
                status.setText('✓ พร้อม')
                status.setStyleSheet('color: %s;' % theme.GREEN)
            elif c['critical']:
                status.setText('✗ ขาด (จำเป็น)')
                status.setStyleSheet('color: %s;' % theme.RED)
            else:
                status.setText('✗ ขาด (ทางเลือก)')
                status.setStyleSheet('color: %s;' % theme.YELLOW)

    def _set_progress(self, value, text):
        self._progress.setValue(int(value))
        if text:
            self._status.setText(text)

    # ── Auto flow ────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        self._start_flow()

    def _start_flow(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if self._flow_started and self._retry_btn.isHidden():
            return
        self._flow_started = True
        self._retry_btn.hide()
        self._set_progress(5, 'กำลังตรวจสอบส่วนประกอบ...')
        QTimer.singleShot(150, self._stage_check)

    def _stage_check(self):
        self._checks = check_dependencies()
        self._refresh()
        pip = missing_pip_packages(self._checks)
        if pip:
            self._stage_pip(pip)
        elif missing_tesseract(self._checks) and _winget_available():
            self._stage_tesseract()
        else:
            self._stage_load_ocr_model()

    def _stage_pip(self, packages):
        self._set_progress(
            15, 'กำลังติดตั้งส่วนประกอบที่ขาด: %s ...' % ', '.join(packages))
        self._animate_to(68)
        self._start_worker('pip', packages, self._after_pip)

    def _after_pip(self, ok):
        self._stop_anim()
        if not ok:
            self._flow_error()
            return
        self._append_log('[ติดตั้งเสร็จสิ้น]')
        self._checks = check_dependencies()
        self._refresh()
        if missing_tesseract(self._checks) and _winget_available():
            self._stage_tesseract()
        else:
            self._stage_load_ocr_model()

    def _stage_tesseract(self):
        self._set_progress(70, 'กำลังติดตั้ง Tesseract OCR (winget)...')
        self._animate_to(90)
        self._start_worker('winget', [], self._after_tesseract)

    def _after_tesseract(self, ok):
        self._stop_anim()
        if ok:
            self._append_log('[ติดตั้ง Tesseract เสร็จสิ้น]')
        else:
            self._append_log('[ข้าม: ไม่สามารถติดตั้ง Tesseract ได้ '
                             '(ระบบอ่านข้อความอาจใช้ไม่ได้)]')
        self._checks = check_dependencies()
        self._refresh()
        self._stage_load_ocr_model()

    # ── โหลด OCR model ล่วงหน้า (ตอนเปิดโปรแกรม) ──────────
    def _stage_load_ocr_model(self):
        """โหลด OCR model — ครั้งแรกโหลดเต็ม+บันทึกแคช, รอบหลังใช้แคชเร็ว."""
        if missing_tesseract(self._checks):
            self._append_log('[ข้าม: ไม่มี Tesseract — OCR ใช้ไม่ได้]')
            self._finish_flow()
            return
        try:
            from vision.ocr_model import get_ocr_model, CACHE_FILE
            model = get_ocr_model()
            if os.path.isfile(CACHE_FILE):
                self._set_progress(95, 'ใช้ OCR model จากแคช (พร้อมใช้ทันที)…')
                self._start_worker('ocr_model', [], self._after_ocr_model)
            else:
                self._set_progress(95, 'กำลังโหลด OCR model (ครั้งแรก)…')
                self._animate_to(99)
                self._start_worker('ocr_model', [], self._after_ocr_model)
        except Exception:
            self._finish_flow()

    def _after_ocr_model(self, ok):
        self._stop_anim()
        if ok:
            self._append_log('[โหลด OCR model เสร็จสิ้น — พร้อมอ่านข้อความ]')
        else:
            self._append_log('[OCR model โหลดไม่สำเร็จ (อ่านข้อความอาจช้า/ใช้ไม่ได้)]')
        self._finish_flow()

    def _finish_flow(self):
        self._stop_anim()
        self._set_progress(100, 'พร้อมใช้งาน กำลังเปิดโปรแกรม...')
        QTimer.singleShot(400, self._on_continue)

    def _flow_error(self):
        self._stop_anim()
        self._progress.setValue(60)
        self._status.setText(
            'ติดตั้งส่วนประกอบไม่สำเร็จ — ตรวจ log ด้านล่าง แล้วลองอีกครั้ง '
            'หรือรันด้วยตนเอง:  python -m pip install pywin32 pytesseract')
        self._log.show()
        self._retry_btn.show()

    # ── Progress animation ───────────────────────────────
    def _animate_to(self, cap):
        self._stop_anim()
        self._anim_cap = cap
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._tick_anim)
        self._progress_timer.start(120)

    def _tick_anim(self):
        cur = self._progress.value()
        if cur < self._anim_cap:
            self._progress.setValue(min(self._anim_cap, cur + 1))

    def _stop_anim(self):
        if self._progress_timer is not None:
            self._progress_timer.stop()
            self._progress_timer.deleteLater()
            self._progress_timer = None

    # ── Worker ───────────────────────────────────────────
    def _start_worker(self, task, packages, on_done):
        self._worker = _InstallWorker(task, packages)
        self._worker.line.connect(self._on_worker_line)
        self._worker.done.connect(on_done)
        self._worker.start()

    def _on_worker_line(self, text):
        self._log.show()
        self._log.appendPlainText(text)
        sb = self._log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _append_log(self, text):
        self._on_worker_line(text)

    # ── Close ────────────────────────────────────────────
    def _on_continue(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self._stop_anim()
        self._proceed = True
        self.continue_signal.emit()

    def _on_cancel(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        self._stop_anim()
        self.cancel_signal.emit()

    def closeEvent(self, event):
        if self._proceed:
            event.accept()
            return
        self._on_cancel()
        event.ignore()


SPLASH_QSS = '''
QDialog {
    background: %(BG)s;
    border: 1px solid %(BORDER)s;
    border-radius: 14px;
}
QLabel#splashTitle {
    color: %(ACCENT_GLOW)s;
    font-size: 16pt;
    font-weight: bold;
}
QLabel#splashSub {
    color: %(FG_DIM)s;
    font-size: 9pt;
}
QLabel#splashStatus {
    color: %(FG)s;
    font-size: 10pt;
    font-weight: bold;
}
QLabel#depName {
    color: %(FG)s;
    font-size: 9pt;
}
QLabel#depStatus {
    font-size: 9pt;
    font-weight: bold;
}
QProgressBar {
    background: %(BG_INPUT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    height: 12px;
    text-align: center;
}
QProgressBar::chunk {
    background: %(ACCENT)s;
    border-radius: 5px;
}
QPushButton#splashClose {
    background: transparent;
    color: %(FG_MUTED)s;
    border: none;
    font-size: 12pt;
    border-radius: 6px;
}
QPushButton#splashClose:hover {
    background: %(RED_BG)s;
    color: %(RED)s;
}
QPlainTextEdit {
    font-family: %(MONO)s;
    font-size: 8pt;
}
''' % {
    'BG': theme.BG, 'BORDER': theme.BORDER, 'BG_INPUT': theme.BG_INPUT,
    'ACCENT': theme.ACCENT, 'ACCENT_GLOW': theme.ACCENT_GLOW,
    'FG': theme.FG, 'FG_DIM': theme.FG_DIM, 'FG_MUTED': theme.FG_MUTED,
    'RED_BG': theme.RED_BG, 'RED': theme.RED, 'MONO': theme.FONT_MONO,
}
