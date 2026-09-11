import io
import json
import os
import socket
import sys
import threading
import time

os.environ["PYTHONIOENCODING"] = "utf-8"

import datetime
import traceback

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.log")

def log_msg(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass

class NullWriter(io.StringIO):
    def write(self, s):
        pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = NullWriter()
else:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = NullWriter()
else:
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import dep_check


def _msgbox(title, text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass


def read_file(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default


def find_free_port(start_port=8000, max_attempts=50):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def wait_for_server(port, timeout=12.0):
    import urllib.request
    url = f"http://127.0.0.1:{port}/api/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


class BootApi:
    def __init__(self):
        self.install_requested = threading.Event()
        self.retry_requested = threading.Event()
        log_msg("BootApi created")

    def request_install(self):
        self.install_requested.set()
        log_msg("user requested auto install")

    def request_retry(self):
        self.retry_requested.set()
        log_msg("user requested recheck")


def _el(window, js):
    try:
        window.evaluate_js(js)
    except Exception:
        pass


def _render(window, result):
    pkgs = result["packages"]
    _el(window, "bootUI.begin(" + json.dumps(pkgs, ensure_ascii=False) + ")")
    ok = 0
    for i, p in enumerate(pkgs):
        _el(window, f"bootUI.row({i}, {str(p['installed']).lower()}, {json.dumps(p['message'], ensure_ascii=False)})")
        if p.get("version"):
            _el(window, f"bootUI.version({i}, {json.dumps(str(p['version']), ensure_ascii=False)})")
        if p["installed"]:
            ok += 1
    _el(window, f"bootUI.setBar({round(100 * ok / max(len(pkgs), 1))})")


def boot_sequence(window, api, ctx):
    try:
        try:
            window.events.loaded.wait(timeout=300)
        except Exception:
            return
        if not window.events.loaded.is_set():
            log_msg("wait loaded timeout 300s")
            return
        log_msg("window loaded - เริ่มตรวจสอบ dependencies")

        while not ctx["stop"].is_set():
            api.install_requested.clear()
            api.retry_requested.clear()

            _el(window, "bootUI.subtitle('กำลังตรวจสอบความพร้อมของโปรแกรม...')")
            result = dep_check.check_installed()
            _render(window, result)
            log_msg(f"check deps: all_ok={result['all_ok']} ({len(result['packages'])} ตัว)")

            if result["all_ok"]:
                break

            _el(window, "bootUI.showMissing()")
            while not ctx["stop"].is_set():
                if api.install_requested.is_set():
                    _el(window, "bootUI.installing()")
                    log_msg("เริ่ม pip install")
                    ok_install = dep_check.run_pip_install(
                        dep_check.REQ_FILE,
                        progress=lambda line: _el(window, "bootUI.installLine(" + json.dumps(line, ensure_ascii=False) + ")"),
                    )
                    log_msg(f"pip install เสร็จ: ok={ok_install}")
                    if not ok_install:
                        _el(window, "bootUI.readyInstall()")
                        _el(window, "bootUI.setStatus('ติดตั้งไม่สำเร็จ โปรดเช็คอินเทอร์เน็ตแล้วกดติดตั้งใหม่ หรือรัน INSTALL.bat')")
                    break
                if api.retry_requested.is_set():
                    break
                time.sleep(0.15)

        if ctx["stop"].is_set():
            return

        _el(window, "bootUI.complete()")

        port = find_free_port(8000)
        try:
            import uvicorn
            server_config = uvicorn.Config(
                "web_server:app",
                host="127.0.0.1",
                port=port,
                reload=False,
                log_level="error",
            )
            server = uvicorn.Server(server_config)
            ctx["server"] = server
            threading.Thread(target=server.run, daemon=True).start()
            log_msg(f"server เริ่มที่พอร์ต {port}")
        except Exception as e:
            log_msg(f"server เริ่มไม่สำเร็จ: {e}\n{traceback.format_exc()}")
            _el(window, "bootUI.setStatus('ไม่สามารถเริ่มเซิร์ฟเวอร์ได้: " + str(e).replace("'", "\\'") + "')")
            return

        if not wait_for_server(port):
            log_msg(f"server ยังไม่พร้อมที่พอร์ต {port}")
            _el(window, "bootUI.setStatus('กำลังเปิดโปรแกรม...')")

        if ctx["stop"].is_set():
            return

        app_url = f"http://127.0.0.1:{port}"
        log_msg(f"open dashboard {app_url}")
        time.sleep(0.6)
        try:
            window.load_url(app_url)
            log_msg("load_url สำเร็จ")
        except Exception as e:
            log_msg(f"load_url ล้มเหลว: {e}\n{traceback.format_exc()}")
            _el(window, "bootUI.setStatus('เปิดหน้าหลักไม่สำเร็จ: " + str(e).replace("'", "\\'") + "')")
    except Exception as e:
        log_msg(f"boot_sequence error: {e}\n{traceback.format_exc()}")


def run_desktop_app():
    log_msg("=== CookieRun Bot เริ่มเปิด ===")
    try:
        import webview
    except Exception as e:
        log_msg(f"import webview ล้มเหลว: {e}\n{traceback.format_exc()}")
        _msgbox("CookieRun Classic Bot", "ไม่พบไลบรารี pywebview\nโปรดรัน INSTALL.bat ก่อนเปิดโปรแกรม")
        print("[ERROR] ไม่พบไลบรารี pywebview")
        return

    base = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base, "bot_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    storage_path = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "CookieRunBot",
        "webview_cache",
    )
    os.makedirs(storage_path, exist_ok=True)

    loader_html = read_file(
        os.path.join(base, "loader.html"),
        "<html><body style='background:#0f172a;color:#fff'>กำลังโหลด...</body></html>",
    )

    ctx = {"server": None, "stop": threading.Event()}
    api = BootApi()

    try:
        window = webview.create_window(
            title="CookieRun Classic Bot",
            html=loader_html,
            js_api=api,
            width=800,
            height=600,
            min_size=(800, 600),
            resizable=False,
            background_color="#0f172a",
            text_select=True,
            confirm_close=False,
        )
        log_msg(f"สร้างหน้าต่างแล้ว: {window}")
    except Exception as e:
        log_msg(f"create_window ล้มเหลว: {e}\n{traceback.format_exc()}")
        _msgbox("CookieRun Classic Bot", f"ไม่สามารถสร้างหน้าต่างโปรแกรมได้:\n{e}\n\nโปรดติดตั้ง Microsoft Edge WebView2 Runtime แล้วลองอีกครั้ง")
        print("[ERROR] create_window:", e)
        return

    def on_closed():
        log_msg("หน้าต่างถูกปิด")
        print("🛑 ปิดโปรแกรม CookieRun Classic Bot")
        bot_engine_stop()

    def bot_engine_stop():
        try:
            from bot_engine import bot_engine
            bot_engine.stop()
        except Exception:
            pass
        server = ctx["server"]
        if server is not None:
            try:
                server.should_exit = True
            except Exception:
                pass
        ctx["stop"].set()

    window.events.closed += on_closed
    threading.Thread(target=boot_sequence, args=(window, api, ctx), daemon=True).start()

    try:
        webview.start(icon=icon_path, storage_path=storage_path, debug=False)
        log_msg("webview.start กลับมาแล้ว (หน้าต่างปิด)")
    except Exception as e:
        log_msg(f"webview.start ล้มเหลว: {e}\n{traceback.format_exc()}")
        _msgbox(
            "CookieRun Classic Bot",
            f"ไม่สามารถเปิดหน้าต่างโปรแกรมได้:\n{e}\n\nโปรดติดตั้ง Microsoft Edge WebView2 Runtime แล้วลองอีกครั้ง",
        )
        print("[ERROR] webview.start:", e)

    bot_engine_stop()
    print("✅ ปิดโปรแกรมเรียบร้อยแล้ว")


if __name__ == "__main__":
    try:
        run_desktop_app()
    except Exception as e:
        log_msg(f"run_desktop_app ตาย: {e}\n{traceback.format_exc()}")
        _msgbox("CookieRun Classic Bot", f"โปรแกรมพบข้อผิดพลาด:\n{e}\n\nดูรายละเอียดในไฟล์ src\\launcher.log")
        raise