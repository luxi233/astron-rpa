import subprocess
from typing import Any

from astronverse.actionlib.types import WinPick
from astronverse.window import ControlInfo, WindowInfoTypeFlag, WindowVisibleTypeFlag, WindowSizeType
from astronverse.window.core import IWindowsCore


class WindowsCore(IWindowsCore):
    @staticmethod
    def info(handler: Any) -> ControlInfo:
        assert isinstance(handler, int)
        win_id = handler

        name = subprocess.check_output(["xdotool", "getwindowname", str(win_id)], encoding="utf-8", errors="replace")
        geom = {}
        output = subprocess.check_output(
            ["xdotool", "getwindowgeometry", "--shell", str(win_id)], shell=True, encoding="utf-8", errors="replace"
        )
        for line in output.splitlines():
            key, value = line.split("=")
            geom[key] = int(value)

        return ControlInfo(
            name=name,
            classname="",  # xprop -id xxx | awk -F '"' '/WM_CLASS/ {print $2}'
            position=(geom["X"], geom["Y"], geom["WIDTH"], geom["HEIGHT"]),
            handler=handler,
        )

    @staticmethod
    def find(pick: WinPick) -> Any:
        name = pick.get("name")
        output = subprocess.check_output(["xdotool", "search", "--name", name], encoding="utf-8", errors="replace")
        window_id = ""
        for line in output.splitlines():
            window_id = line
            # 使用最后一个
        if window_id:
            return int(window_id)
        return None

    @staticmethod
    def is_active(handler: Any) -> bool:
        """
        is_active 判断窗口是否为前台激活窗口
        """
        assert isinstance(handler, int)
        output = subprocess.check_output(["xdotool", "getactivewindow"], encoding="utf-8", errors="replace")
        return int(output.strip()) == handler

    @staticmethod
    def top(handler: Any):
        assert isinstance(handler, int)
        win_id = handler
        subprocess.check_output(
            ["xdotool", "windowraise", str(win_id)],
            encoding="utf-8",
            errors="replace",
        )

    @staticmethod
    def close(handler: Any):
        assert isinstance(handler, int)
        win_id = handler
        subprocess.check_output(["xdotool", "windowclose", str(win_id)], encoding="utf-8", errors="replace")

    @staticmethod
    def size(
        handler: Any,
        size_type: WindowSizeType = WindowSizeType.MAX,
        width: int = 0,
        height: int = 0,
    ):
        assert isinstance(handler, int)
        win_id = handler

        if size_type == WindowSizeType.CUSTOM:
            subprocess.check_output(
                ["xdotool", "windowsize", str(win_id), str(width), str(height)], encoding="utf-8", errors="replace"
            )
        elif size_type == WindowSizeType.MAX:
            subprocess.check_output(
                ["xdotool", "windowsize", str(win_id), "100%", "100%"], encoding="utf-8", errors="replace"
            )
        elif size_type == WindowSizeType.MIN:
            subprocess.check_output(["xdotool", "windowminimize", str(win_id)], encoding="utf-8", errors="replace")

    @staticmethod
    def toControl(handler: Any) -> Any:
        raise NotImplementedError

    @staticmethod
    def find_list(title_contains: str = "") -> list[tuple[str, str]]:
        """xdotool 枚举窗口，按标题包含匹配，返回 (标题, 类名) 列表"""
        results = []
        try:
            output = subprocess.check_output(
                ["xdotool", "search", "--onlyvisible", "--name", "."],
                encoding="utf-8",
                errors="replace",
            )
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                win_id = int(line)
                title = subprocess.check_output(
                    ["xdotool", "getwindowname", str(win_id)], encoding="utf-8", errors="replace"
                ).strip()
                if not title:
                    continue
                if title_contains and title_contains not in title:
                    continue
                results.append((title, ""))
        except Exception:
            pass
        return results

    @staticmethod
    def info_value(handler: Any, info_type: WindowInfoTypeFlag) -> Any:
        assert isinstance(handler, int)
        win_id = handler
        if info_type == WindowInfoTypeFlag.TITLE:
            return subprocess.check_output(
                ["xdotool", "getwindowname", str(win_id)], encoding="utf-8", errors="replace"
            ).strip()
        elif info_type == WindowInfoTypeFlag.CLASS_NAME:
            try:
                output = subprocess.check_output(
                    ["xdotool", "getwindowclassname", str(win_id)], encoding="utf-8", errors="replace"
                )
                return output.strip()
            except Exception:
                return ""
        elif info_type == WindowInfoTypeFlag.PROCESS_NAME:
            try:
                output = subprocess.check_output(
                    ["xdotool", "getwindowpid", str(win_id)], encoding="utf-8", errors="replace"
                )
                pid = output.strip()
                link = subprocess.check_output(["readlink", f"/proc/{pid}/exe"], encoding="utf-8", errors="replace")
                return link.strip().split("/")[-1]
            except Exception:
                return ""
        else:  # RECT
            geom = {}
            output = subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", str(win_id)], encoding="utf-8", errors="replace"
            )
            for line in output.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    geom[key] = int(value)
            return [
                geom.get("X", 0),
                geom.get("Y", 0),
                geom.get("X", 0) + geom.get("WIDTH", 0),
                geom.get("Y", 0) + geom.get("HEIGHT", 0),
            ]

    @staticmethod
    def move(handler: Any, x: int, y: int):
        assert isinstance(handler, int)
        subprocess.check_output(
            ["xdotool", "windowmove", str(handler), str(int(x)), str(int(y))],
            encoding="utf-8",
            errors="replace",
        )

    @staticmethod
    def set_visible(handler: Any, visible_type: WindowVisibleTypeFlag):
        assert isinstance(handler, int)
        action = "windowmap" if visible_type == WindowVisibleTypeFlag.SHOW else "windowunmap"
        subprocess.check_output(["xdotool", action, str(handler)], encoding="utf-8", errors="replace")

    @staticmethod
    def get_selected_text() -> str:
        # xdotool 无选中文本API，用 xclip 读取选区（XA_PRIMARY）
        try:
            return subprocess.check_output(["xclip", "-selection", "primary", "-o"], encoding="utf-8", errors="replace")
        except Exception:
            return ""
