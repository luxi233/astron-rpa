import platform
import subprocess


def get_selected_files_win() -> list:
    """获取Windows资源管理器/桌面当前选中的文件(夹)路径列表"""
    import ctypes
    import ctypes.wintypes

    import pythoncom
    import win32com.client

    def get_foreground_class() -> str:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        fg_class = get_foreground_class()

        # 前台是桌面(Progman/WorkerW)时，取桌面选中项
        if fg_class in ("Progman", "WorkerW"):
            try:
                # SWC_DESKTOP=0x08, SWFO_INCLUDEHIDDEN=0x01
                desktop_wnd = shell.FindWindowSW(0, 0, 0x08, None, 0x01)
                return [str(item.Path) for item in desktop_wnd.Document.SelectedItems()]
            except Exception:
                pass

        # 前台是资源管理器窗口时，匹配前台句柄
        hwnd_fg = ctypes.windll.user32.GetForegroundWindow()
        for window in shell.Windows():
            try:
                if int(window.HWND) == int(hwnd_fg):
                    return [str(item.Path) for item in window.Document.SelectedItems()]
            except Exception:
                continue
        return []
    finally:
        pythoncom.CoUninitialize()


def get_selected_files_mac() -> list:
    """获取macOS Finder当前选中的文件(夹)路径列表"""
    # 注意: selection 返回的是Finder引用而非列表, 直接repeat/count会得到0, 需先 as alias list
    script = (
        'tell application "Finder"\n'
        '    set output to ""\n'
        "    set sel to {}\n"
        "    try\n"
        "        set sel to get selection as alias list\n"
        "    end try\n"
        "    repeat with a in sel\n"
        "        set output to output & POSIX path of a & linefeed\n"
        "    end repeat\n"
        "    return output\n"
        "end tell"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_selected_files() -> list:
    """获取当前系统文件管理器中选中的文件(夹)路径列表"""
    system = platform.system()
    if system == "Windows":
        return get_selected_files_win()
    if system == "Darwin":
        return get_selected_files_mac()
    raise NotImplementedError(f"unsupported platform: {system}")
