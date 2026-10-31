# -*- coding: utf-8 -*-
"""
新能源车价计算器 · 桌面版启动器

把单文件 HTML 装进 WebView2 窗口，做成免安装 exe。

设计要点：
1. HTML 首次运行时落到固定的 %LOCALAPPDATA% 路径，之后始终从同一路径加载。
   file:// 源不变 + 固定 profile，localStorage 里的「已保存方案」才能跨次启动保留。
   （若改用随机端口 http 服务，端口一变 origin 就变，方案会全丢。）
2. 单实例：WebView2 的 user data 目录同一个进程只应有一份，双击两次会互相锁死，
   所以用命名互斥体挡住第二次启动，并把已有窗口拉到前台。
3. 无控制台，异常写入 last_error.log 并弹窗，否则用户只会看到「双击没反应」。
"""
import ctypes
import json
import os
import sys
import pathlib
import traceback

APP_NAME = "新能源车价计算器"
APP_ID = "NEVPriceCalc"
HTML_SRC_NAME = "车价计算器.html"
HTML_DST_NAME = "app.html"
MUTEX_NAME = "Local\\NEVPriceCalc_SingleInstance"

_MUTEX = None  # 持有引用，防止被 GC 关闭


def base_dir():
    """打包后资源在 _MEIPASS；开发时优先脚本上一级。"""
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.exists(os.path.join(parent, HTML_SRC_NAME)):
        return parent
    return here


def data_dir():
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(root, APP_ID)
    os.makedirs(d, exist_ok=True)
    return d


def sha256_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_html():
    """把内置 HTML 同步到固定路径，内容变了才覆盖。"""
    src = os.path.join(base_dir(), HTML_SRC_NAME)
    if not os.path.exists(src):
        raise FileNotFoundError("找不到内置页面：%s" % src)
    dst = os.path.join(data_dir(), HTML_DST_NAME)
    need = True
    if os.path.exists(dst):
        try:
            need = sha256_of(src) != sha256_of(dst)
        except OSError:
            need = True
    if need:
        with open(src, "rb") as f:
            payload = f.read()
        tmp = dst + ".tmp"
        with open(tmp, "wb") as f:
            f.write(payload)
        os.replace(tmp, dst)
    return dst


def already_running():
    """已有实例就把它拉到前台并返回 True。"""
    global _MUTEX
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX = k32.CreateMutexW(None, False, MUTEX_NAME)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        u32 = ctypes.windll.user32
        hwnd = u32.FindWindowW(None, APP_NAME)
        if hwnd:
            u32.ShowWindow(hwnd, 9)      # SW_RESTORE
            u32.SetForegroundWindow(hwnd)
        return True
    return False


def log_error(exc_text):
    try:
        with open(os.path.join(data_dir(), "last_error.log"), "a", encoding="utf-8") as f:
            f.write(exc_text + "\n" + "-" * 60 + "\n")
    except OSError:
        pass


def show_error(msg):
    try:
        ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME + " · 启动失败", 0x10)
    except Exception:  # noqa: BLE001
        pass


# ---------------- 窗口几何记忆 ----------------
GEOM_FILE = "window.json"


def load_geom():
    try:
        with open(os.path.join(data_dir(), GEOM_FILE), "r", encoding="utf-8") as f:
            g = json.load(f)
        w, h = int(g.get("w", 0)), int(g.get("h", 0))
        if w >= 920 and h >= 640:
            return {
                "width": w, "height": h,
                "x": g.get("x"), "y": g.get("y"),
                "maximized": bool(g.get("maximized")),
            }
    except Exception:  # noqa: BLE001
        pass
    return {"width": 1260, "height": 940, "x": None, "y": None, "maximized": False}


def save_geom(win):
    try:
        state = {"w": win.width, "h": win.height, "x": win.x, "y": win.y, "maximized": False}
        try:
            state["maximized"] = win.state == 1  # pywebview: 1 = maximized
        except Exception:  # noqa: BLE001
            pass
        with open(os.path.join(data_dir(), GEOM_FILE), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:  # noqa: BLE001
        pass


def run():
    import webview

    html_path = ensure_html()
    profile = os.path.join(data_dir(), "profile")
    os.makedirs(profile, exist_ok=True)

    geom = load_geom()
    win = webview.create_window(
        APP_NAME,
        pathlib.Path(html_path).as_uri(),
        width=geom["width"],
        height=geom["height"],
        x=geom["x"],
        y=geom["y"],
        min_size=(920, 640),
        background_color="#f5f6f8",
        text_select=True,
        maximized=geom["maximized"],
    )

    def on_closing():
        save_geom(win)

    try:
        win.events.closing += on_closing
    except Exception:  # noqa: BLE001
        pass

    webview.start(private_mode=False, storage_path=profile, debug=False)
    return 0


def main():
    if already_running():
        return 0
    try:
        return run()
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        log_error(tb)
        tail = tb.strip().splitlines()[-1] if tb.strip() else "未知错误"
        show_error(
            "程序启动失败：\n\n%s\n\n详细信息已写入：\n%s\n\n"
            "最常见原因是缺少 Microsoft Edge WebView2 运行时，"
            "可从微软官网下载安装后重试。" % (tail, os.path.join(data_dir(), "last_error.log"))
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
