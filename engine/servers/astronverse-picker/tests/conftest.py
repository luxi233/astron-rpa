"""拾取器单元测试夹具。

拾取器大量模块依赖 Windows 专属库(uiautomation/ctypes.wintypes/ctypes.windll),
本套件在非 Windows 平台通过 stub 这些依赖实现纯逻辑模块的可测性;
真正的窗口/UIA 交互不在单元测试范围(需 Windows 真机)。
"""

import ctypes
import sys
import types


def _install_win_stubs() -> None:
    # --- ctypes.wintypes: 非Windows平台 import 即抛 ValueError ---
    if "ctypes.wintypes" not in sys.modules or not hasattr(sys.modules["ctypes.wintypes"], "HWND"):
        wt = types.ModuleType("ctypes.wintypes")
        for name in ["HWND", "LPARAM", "WPARAM", "DWORD", "LONG", "ULONG", "BOOL", "HANDLE"]:
            setattr(wt, name, ctypes.c_void_p)
        sys.modules["ctypes.wintypes"] = wt

    # --- ctypes.windll: 仅Windows存在, browser.py 模块级访问 windll.user32 ---
    if not hasattr(ctypes, "windll"):
        ctypes.windll = type("_StubWindll", (), {"__getattr__": staticmethod(lambda name: ctypes.c_void_p())})()  # type: ignore[attr-defined]

    # --- uiautomation: win32 条件依赖 ---
    if "uiautomation" not in sys.modules:
        ua = types.ModuleType("uiautomation")

        class _Control:  # 最小 Control 桩
            pass

        ua.Control = _Control
        ua.ControlType = types.SimpleNamespace(DocumentControl="DocumentControl", PaneControl="PaneControl")
        sys.modules["uiautomation"] = ua


_install_win_stubs()
