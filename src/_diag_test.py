import threading
import time
import webview

loader = open("loader.html", "r", encoding="utf-8").read()

try:
    w = webview.create_window(
        title="TEST CookieRun Bot",
        html=loader,
        width=820,
        height=620,
        background_color="#0f172a",
        text_select=True,
    )
    print("WINDOW CREATED:", w)
    print("events ok:", w.events)
    def close_later():
        time.sleep(5)
        try:
            w.destroy()
            print("DESTROYED")
        except Exception as e:
            print("DESTROY ERR", e)
    threading.Thread(target=close_later, daemon=True).start()
    webview.start(debug=False)
    print("START RETURNED OK")
except Exception as e:
    import traceback
    traceback.print_exc()