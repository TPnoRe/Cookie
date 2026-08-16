"""Cookie Run Classic Bot — ตัวเริ่มโปรแกรม.

ลำดับการเปิด:
1. ตรวจสอบ dependencies (pywin32 / OCR / ...)
2. เปิดหน้าต่าง Splash (ติดตั้งส่วนที่ขาดได้ถ้าจำเป็น)
3. กด "เปิดโปรแกรม" → เปิดหน้าต่างหลัก

รัน:  python main.pyw
"""
import os
import sys
import traceback
import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash.log')


def _install_excepthook():
    def _hook(exc_type, exc_value, exc_tb):
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write('=== Crash === %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.write('\n')
    sys.excepthook = _hook


def _launch_main(qt_app, splash):
    """เปิดหน้าต่างหลักหลังผู้ใช้กด "เปิดโปรแกรม" บน splash."""
    splash.close()
    from core.window import AppWindow
    from ui.app import App
    window = AppWindow(title='Cookie Run Classic Bot')
    App(window)
    window.run()


def main():
    _install_excepthook()
    from core.window import enable_dpi_awareness
    enable_dpi_awareness()

    from PyQt6.QtWidgets import QApplication
    qt_app = QApplication(sys.argv)
    qt_app.setStyle('Fusion')

    from core.dependencies import check_dependencies
    from ui.splash import SplashWindow

    splash = SplashWindow(check_dependencies())
    splash.continue_signal.connect(lambda: _launch_main(qt_app, splash))
    splash.cancel_signal.connect(qt_app.quit)
    splash.show()
    qt_app.exec()


if __name__ == '__main__':
    main()
