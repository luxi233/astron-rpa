"""屏幕保护核心模块: 自实现全屏置顶屏保窗口(独立进程) + 屏保提示文字管理"""

import os
import subprocess
import sys
import tempfile

# 进程标记, 用于跨进程查找屏保进程(唤起/关闭)
SCREENSAVER_MARK = "astron_screensaver_proc"
# 屏保提示文字文件(进程间共享)
TIP_FILE = os.path.join(tempfile.gettempdir(), "astron_screensaver_tip.txt")

# 独立进程运行的全屏屏保窗口脚本(tkinter黑窗 + 提示文字轮询热更新 + 任意键鼠退出)
SCREENSAVER_SCRIPT = r"""
import os, sys, tkinter as tk

TIP_FILE = sys.argv[1] if len(sys.argv) > 1 else ""
root = tk.Tk()
root.title("astron_screensaver")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.configure(bg="black")
root.config(cursor="none")

label = tk.Label(root, text="", fg="white", bg="black",
                 font=("Microsoft YaHei", "PingFang SC", 28), wraplength=root.winfo_screenwidth() - 100,
                 justify="center")
label.place(relx=0.5, rely=0.5, anchor="center")

def refresh_tip():
    text = ""
    if TIP_FILE and os.path.exists(TIP_FILE):
        try:
            with open(TIP_FILE, encoding="utf-8") as f:
                text = f.read().strip()
        except Exception:
            text = ""
    if label.cget("text") != text:
        label.config(text=text)
    root.after(500, refresh_tip)

def quit_screensaver(_event=None):
    root.destroy()

root.bind("<Any-KeyPress>", quit_screensaver)
root.bind("<Button-1>", quit_screensaver)
root.bind("<Motion>", lambda e: None)  # 鼠标移动不退出, 点击才退出
refresh_tip()
root.mainloop()
"""


def _read_tip() -> str:
    try:
        if os.path.exists(TIP_FILE):
            with open(TIP_FILE, encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def write_tip(text: str) -> None:
    """写入屏保提示文字(屏保运行中会自动热更新)"""
    os.makedirs(os.path.dirname(TIP_FILE), exist_ok=True)
    with open(TIP_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def clear_tip() -> bool:
    """清空屏保提示文字, 返回是否原本存在"""
    existed = os.path.exists(TIP_FILE)
    if existed:
        try:
            os.remove(TIP_FILE)
        except Exception:
            pass
    return existed


def get_tip() -> str:
    return _read_tip()


def find_screensaver_processes() -> list:
    """查找运行中的屏保窗口进程"""
    import psutil

    result = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            if any(SCREENSAVER_MARK in str(arg) for arg in cmdline):
                result.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def is_running() -> bool:
    return len(find_screensaver_processes()) > 0


def start_screensaver() -> None:
    """唤起屏幕保护(独立进程全屏置顶黑窗, 显示已设置的提示文字)"""
    if is_running():
        return  # 已在运行, 不重复唤起
    script_path = os.path.join(tempfile.gettempdir(), "astron_screensaver_win.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(SCREENSAVER_SCRIPT)
    subprocess.Popen(
        [sys.executable, script_path, TIP_FILE, SCREENSAVER_MARK],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_screensaver() -> bool:
    """关闭已唤起的屏保窗口, 返回是否找到并关闭了屏保"""
    procs = find_screensaver_processes()
    for proc in procs:
        try:
            proc.terminate()
        except Exception:
            pass
    _, alive = psutil_wait(procs, timeout=3)
    for proc in alive:
        try:
            proc.kill()
        except Exception:
            pass
    return len(procs) > 0


def psutil_wait(procs, timeout=3):
    """等待进程退出, 返回(已退出, 仍存活)"""
    import psutil

    gone, alive = [], []
    try:
        gone, alive = psutil.wait_procs(procs, timeout=timeout)
    except Exception:
        alive = procs
    return gone, alive
