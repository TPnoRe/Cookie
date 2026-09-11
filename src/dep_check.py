import importlib.metadata
import importlib.util
import os
import re
import subprocess
import sys

REQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
PACKAGE_MODULE_OVERRIDES = {
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "pywebview": "webview",
    "pillow": "PIL",
    "pyyaml": "yaml",
}


def parse_requirements(path=REQ_FILE):
    packages = []
    if not os.path.isfile(path):
        return packages
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#")[0].strip()
            if not line:
                continue
            line = re.sub(r"\s*;\s*.*$", "", line)
            line = line.split("[")[0]
            line = re.split(r"\s+", line)[0]
            line = re.sub(r"-{2,}.*$", "", line).strip()
            if line:
                packages.append(line)
    return packages


def _module_name(pkg_line):
    name = re.split(r"[<>=!~]", pkg_line)[0].strip().lower()
    return PACKAGE_MODULE_OVERRIDES.get(name, name.replace("-", "_"))


_REQ_RE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*([<>=!~]{1,2})\s*([0-9A-Za-z.]+)?\s*$")


def _split_requirement(req):
    m = _REQ_RE.match(req)
    if not m:
        return req, None, None
    return m.group(1), m.group(2), m.group(3)


def _parse_num(v):
    return [int(p) for p in re.findall(r"\d+", v)] or [0]


def _ver_cmp(a, b):
    x, y = _parse_num(a), _parse_num(b)
    n = max(len(x), len(y))
    x += [0] * (n - len(x))
    y += [0] * (n - len(y))
    return (x > y) - (x < y)


def version_ok(installed, op, required):
    if not op or not required:
        return True
    c = _ver_cmp(installed, required)
    if op == ">=":
        return c >= 0
    if op == ">":
        return c > 0
    if op == "<=":
        return c <= 0
    if op == "<":
        return c < 0
    if op == "==":
        return c == 0
    if op == "!=":
        return c != 0
    if op == "~=":
        return c >= 0
    return True


def check_installed(path=REQ_FILE):
    packages = parse_requirements(path)
    results = []
    all_ok = True
    for req in packages:
        name, op, required = _split_requirement(req)
        module = _module_name(req)
        ok = True
        installed_version = None
        message = "พร้อมใช้งาน"
        try:
            if importlib.util.find_spec(module) is None:
                raise ImportError
        except Exception:
            ok = False
            all_ok = False
            message = "ยังไม่ได้ติดตั้ง"
        else:
            try:
                installed_version = importlib.metadata.version(name) or "?"
            except Exception:
                installed_version = "?"
            if op and required and installed_version != "?" and not version_ok(installed_version, op, required):
                ok = False
                all_ok = False
                message = f"ต้องการเวอร์ชัน {req} แต่พบ {installed_version}"
        results.append({
            "name": req,
            "module": module,
            "installed": ok,
            "version": installed_version or "",
            "message": message,
        })
    return {"all_ok": all_ok, "packages": results}


def run_pip_install(path=REQ_FILE, progress=None):
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", path]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
    except Exception as e:
        if progress:
            progress(str(e))
        return False
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if progress:
            try:
                progress(line.rstrip())
            except Exception:
                pass
    code = proc.wait()
    return code == 0


def summarize(result):
    missing = [p for p in result["packages"] if not p["installed"]]
    return {
        "total": len(result["packages"]),
        "ok": len(result["packages"]) - len(missing),
        "missing": missing,
        "all_ok": result["all_ok"],
    }