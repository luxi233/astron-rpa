from typing import Any

import win32com.client
import win32con
import win32gui
import win32process
from astronverse.actionlib.types import WinPick
from astronverse.window import ControlInfo, WalkControlInfo, WindowInfoTypeFlag, WindowVisibleTypeFlag, WindowSizeType
from astronverse.window.core import IUITreeCore, IWindowsCore
from astronverse.window.error import *


class WindowsCore(IWindowsCore):
    @staticmethod
    def toControl(handler: Any) -> Any:
        import uiautomation

        return uiautomation.ControlFromHandle(handler)

    @staticmethod
    def find(pick: WinPick) -> Any:
        """
        _find 查找 handle
        """
        wnd_name = pick.get("elementData", {}).get("path", [])[0].get("name", "")
        wnd_class_name = pick.get("elementData", {}).get("path", [])[0].get("cls", "")

        window_handle = win32gui.FindWindow(wnd_class_name, wnd_name)
        if not window_handle:
            window_handle = win32gui.FindWindowEx(None, None, None, wnd_name)
            if not window_handle:
                raise BaseException(WINDOW_NO_FIND, "未找到目标窗口{}".format(pick))
        return window_handle

    @staticmethod
    def is_active(handler: Any) -> bool:
        """
        is_active 判断窗口是否为前台激活窗口
        """
        return win32gui.GetForegroundWindow() == handler

    @staticmethod
    def info(handler: Any) -> ControlInfo:
        """
        info 查询信息
        """
        return ControlInfo(
            name=win32gui.GetWindowText(handler),
            classname=win32gui.GetWindowText(handler),
            position=win32gui.GetWindowRect(handler),
            handler=handler,
        )

    @staticmethod
    def top(handler: Any):
        """
        top 置顶
        """
        if win32gui.IsIconic(handler):
            win32gui.ShowWindow(handler, win32con.SW_NORMAL)
        else:
            # 结合键盘事件
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("%")
            win32gui.SetForegroundWindow(handler)

    @staticmethod
    def close(handler: Any):
        """
        close 关闭
        """
        win32gui.SendMessage(handler, win32con.WM_CLOSE, None, None)

    @staticmethod
    def size(
        handler: Any,
        size_type: WindowSizeType = WindowSizeType.MAX,
        width: int = 0,
        height: int = 0,
    ):
        """
        size 设置尺寸
        """
        if size_type == WindowSizeType.CUSTOM:
            win32gui.ShowWindow(handler, win32con.SW_RESTORE)

            rect = win32gui.GetWindowRect(handler)
            win32gui.SetWindowPos(
                handler,
                win32con.HWND_NOTOPMOST,
                rect[0],
                rect[1],
                width,
                height,
                win32con.SWP_SHOWWINDOW,
            )
        elif size_type == WindowSizeType.MAX:
            win32gui.ShowWindow(handler, win32con.SW_MAXIMIZE)
            # 兜底
            rect = win32gui.GetWindowRect(handler)
            x = rect[0]
            y = rect[1]
            w = rect[2] - x
            h = rect[3] - y
            win32gui.SetWindowPos(
                handler,
                win32con.HWND_NOTOPMOST,
                x,
                y,
                w,
                h,
                win32con.SWP_SHOWWINDOW,
            )
        elif size_type == WindowSizeType.MIN:
            win32gui.ShowWindow(handler, win32con.SW_MINIMIZE)

    @staticmethod
    def find_list(title_contains: str = "") -> list[tuple[str, str]]:
        """
        find_list 按标题包含匹配枚举所有可见顶层窗口，返回 (标题, 类名) 列表
        """
        results = []

        def _enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            if title_contains and title_contains not in title:
                return
            results.append((title, win32gui.GetClassName(hwnd)))

        win32gui.EnumWindows(_enum_handler, None)
        return results

    @staticmethod
    def info_value(handler: Any, info_type: WindowInfoTypeFlag) -> Any:
        """
        info_value 按类型获取窗口信息（标题/类名/进程名/位置尺寸）
        """
        if info_type == WindowInfoTypeFlag.TITLE:
            return win32gui.GetWindowText(handler)
        elif info_type == WindowInfoTypeFlag.CLASS_NAME:
            return win32gui.GetClassName(handler)
        elif info_type == WindowInfoTypeFlag.PROCESS_NAME:
            import os

            _, pid = win32process.GetWindowThreadProcessId(handler)
            if not pid:
                return ""
            import win32api

            process_name = ""
            try:
                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle:
                    process_name = win32process.GetModuleFileNameEx(handle, 0)
                    win32api.CloseHandle(handle)
            except Exception:
                pass
            if not process_name:
                try:
                    import psutil

                    process_name = psutil.Process(pid).exe()
                except Exception:
                    process_name = str(pid)
            return os.path.basename(process_name) if process_name else ""
        else:  # RECT
            left, top, right, bottom = win32gui.GetWindowRect(handler)
            return [int(left), int(top), int(right), int(bottom)]

    @staticmethod
    def move(handler: Any, x: int, y: int):
        """
        move 移动窗口位置（保持窗口尺寸不变）
        """
        if win32gui.IsIconic(handler):
            win32gui.ShowWindow(handler, win32con.SW_RESTORE)
        rect = win32gui.GetWindowRect(handler)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        win32gui.SetWindowPos(
            handler,
            0,
            int(x),
            int(y),
            width,
            height,
            win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW,
        )

    @staticmethod
    def set_visible(handler: Any, visible_type: WindowVisibleTypeFlag):
        """
        set_visible 设置窗口显示/隐藏
        """
        if visible_type == WindowVisibleTypeFlag.SHOW:
            win32gui.ShowWindow(handler, win32con.SW_SHOW)
        else:
            win32gui.ShowWindow(handler, win32con.SW_HIDE)

    @staticmethod
    def get_selected_text() -> str:
        """
        get_selected_text 获取当前激活窗口中被选中的文本（UIA TextPattern 优先，剪贴板兜底）
        """
        import time as _time

        # 1. UIA TextPattern 方式
        try:
            import uiautomation

            focused = uiautomation.GetFocusedControl()
            text_pattern = focused.GetTextPattern()
            if text_pattern:
                selections = text_pattern.GetSelection()
                texts = []
                for text_range in selections:
                    texts.append(text_range.GetText(-1))
                return "".join(texts)
        except Exception:
            pass

        # 2. 剪贴板兜底：保存原剪贴板 → Ctrl+C → 读取 → 还原
        import pyautogui

        backup = None
        try:
            import win32clipboard
            import win32con as _wc

            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(_wc.CF_UNICODETEXT):
                backup = win32clipboard.GetClipboardData(_wc.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception:
            backup = None

        pyautogui.hotkey("ctrl", "c")
        _time.sleep(0.3)

        selected = ""
        try:
            import win32clipboard
            import win32con as _wc

            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(_wc.CF_UNICODETEXT):
                selected = win32clipboard.GetClipboardData(_wc.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception:
            selected = ""

        # 还原剪贴板
        if backup is not None:
            try:
                import win32clipboard
                import win32con as _wc

                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(_wc.CF_UNICODETEXT, backup)
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        return selected


class UITreeCore(IUITreeCore):
    @staticmethod
    def GetRootControl() -> Any:
        import uiautomation

        return uiautomation.GetRootControl()

    @staticmethod
    def WalkControl(control: Any, includeTop: bool = False, maxDepth: int = 0xFFFFFFFF):
        """
        WalkControl Control遍历
        """
        import uiautomation

        for control, depth in uiautomation.WalkControl(control, includeTop=includeTop, maxDepth=maxDepth):
            yield WalkControlInfo(
                name=control.Name,
                classname=control.ClassName,
                position=control.BoundingRectangle,
                control_type=control.ControlType,
                control_type_name=control.LocalizedControlType,
                control=control,
                depth=depth,
                automation_id=control.AutomationId,
            )

    @staticmethod
    def toHandler(control) -> Any:
        return control.NativeWindowHandle

    @staticmethod
    def setAction(control) -> bool:
        return control.SetActive()
