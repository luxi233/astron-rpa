"""桌面相似元素匹配链路回归测试。

覆盖"获取相似元素列表(桌面)"拾取时报"元素无法找到"的三个根因修复:
1. 窗口搜索过滤: name/cls 为 None(被禁用)时不应过滤掉全部窗口
2. __find_one__ 单层路径(仅窗口层)应能返回窗口控件(截短降级兜底)
3. __find_similar__ 父路径截短时, 被截掉的层应前插到区分链, 否则层级错位匹配必空
"""

import sys
import types
from types import SimpleNamespace

import pytest


def _install_locator_win_stubs() -> None:
    """locator/utils/window.py 与 picker/utils/window.py 的 win32 依赖桩(非Windows平台)"""

    def _stub_module(name: str, **attrs) -> types.ModuleType:
        mod = sys.modules.get(name)
        if mod is not None:
            return mod
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        mod.__getattr__ = lambda attr_name: 0  # type: ignore[method-assign]
        sys.modules[name] = mod
        return mod

    # win32api / win32con / win32gui / win32print / win32process
    _stub_module("win32api", GetSystemMetrics=lambda m: 1920)
    _stub_module("win32con")
    _stub_module(
        "win32gui",
        GetParent=lambda h: 0,
        EnumWindows=lambda cb, acc: acc.extend([1001, 1002]),
        SetForegroundWindow=lambda h: None,
        IsIconic=lambda h: False,
        ShowWindow=lambda h, cmd: None,
    )
    _stub_module("win32print")
    _stub_module("win32process", GetWindowThreadProcessId=lambda h: (0, 1234))

    # win32com / win32com.client
    win32com = _stub_module("win32com")
    if "win32com.client" not in sys.modules:
        client = types.ModuleType("win32com.client")
        client.Dispatch = lambda *a, **k: SimpleNamespace(SendKeys=lambda *a, **k: None)
        sys.modules["win32com.client"] = client
        win32com.client = client

    # pygetwindow / pygetwindow._pygetwindow_win
    pygetwindow = _stub_module("pygetwindow", getWindowsWithTitle=lambda title: [])
    if "pygetwindow._pygetwindow_win" not in sys.modules:
        win_mod = types.ModuleType("pygetwindow._pygetwindow_win")

        class _Win32Window:
            def __init__(self, handle):
                self._hWnd = handle
                self.left, self.top, self.right, self.bottom = 0, 0, 100, 100
                self.isMinimized = False

            def minimize(self):
                self.isMinimized = True

            def restore(self):
                self.isMinimized = False

            def activate(self):
                pass

        win_mod.Win32Window = _Win32Window
        win_mod.isWindowVisible = lambda h: True
        sys.modules["pygetwindow._pygetwindow_win"] = win_mod
        pygetwindow._pygetwindow_win = win_mod

    # 扩展 conftest 的 uiautomation 桩: 补 ControlFromHandle
    ua = sys.modules.get("uiautomation")
    if ua is not None and not hasattr(ua, "ControlFromHandle"):
        ua.ControlFromHandle = lambda handle: None


_install_locator_win_stubs()

from astronverse.locator.utils import window as locator_window_mod  # noqa: E402
from astronverse.locator.core import uia_locator as uia_mod  # noqa: E402
from astronverse.picker.engines.uia_picker import UIAPicker  # noqa: E402


# ---------------- 通用构造工具 ----------------


def _node(tag, cls=None, name=None, index=0, disable_keys=None, **extra):
    node = {"tag_name": tag, "checked": True, "disable_keys": disable_keys or [], "index": index}
    if cls is not None:
        node["cls"] = cls
    if name is not None:
        node["name"] = name
    node.update(extra)
    return node


def _similar_ele(**overrides):
    """构造相似拾取产出的泛化路径: [Win(sp), Pane(sp), List(sp), ListItem(区分层tag-only)]"""
    win_name = overrides.get("win_name", "Doc1")
    return {
        "app": "app",
        "type": "uia",
        "picker_type": "SIMILAR",
        "path": [
            _node("WindowControl", cls="AppWin", name=win_name, index=0, similar_parent=True),
            _node("PaneControl", cls="PaneCtl", name="Main", index=0, similar_parent=True),
            _node("ListControl", cls="ListCtl", name="任务列表", index=0, similar_parent=True),
            _node(
                "ListItemControl",
                cls="ListItemCtl",
                name="A",
                index=0,
                disable_keys=["cls", "name", "value", "index"],
            ),
        ],
    }


class FakeControl(sys.modules["uiautomation"].Control):
    """最小 UIA Control 桩: 支持兄弟遍历/父子遍历/属性访问"""

    def __init__(self, tag, cls="", name="", children=None, handle=None):
        self.ControlTypeName = tag
        self.ClassName = cls
        self.Name = name
        self.NativeWindowHandle = handle or 0
        self.ProcessId = 1234
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=100, bottom=100)
        self._children = children or []
        self._parent = None
        for child in self._children:
            child._parent = self

    def GetFirstChildControl(self):
        return self._children[0] if self._children else None

    def _siblings(self):
        return self._parent._children if self._parent else [self]

    def GetNextSiblingControl(self):
        sibs = self._siblings()
        idx = sibs.index(self)
        return sibs[idx + 1] if idx + 1 < len(sibs) else None

    def GetPreviousSiblingControl(self):
        sibs = self._siblings()
        idx = sibs.index(self)
        return sibs[idx - 1] if idx > 0 else None

    def GetValuePattern(self):
        raise NotImplementedError("no value pattern")


def _build_tree(pane_name="Main", list_name="任务列表"):
    list_ctrl = FakeControl(
        "ListControl",
        cls="ListCtl",
        name=list_name,
        children=[
            FakeControl("ListItemControl", cls="ListItemCtl", name="A"),
            FakeControl("ListItemControl", cls="ListItemCtl", name="B"),
            FakeControl("ListItemControl", cls="ListItemCtl", name="C"),
        ],
    )
    pane = FakeControl("PaneControl", cls="PaneCtl", name=pane_name, children=[list_ctrl])
    win = FakeControl("WindowControl", cls="AppWin", name="Doc1", children=[pane], handle=1001)
    return win, pane, list_ctrl


@pytest.fixture()
def patch_locator_env(monkeypatch):
    """把 __find_one__ 的窗口/句柄依赖替换为受控桩"""

    def _patch(win_controls, handles=None):
        handle_map = {ctrl.NativeWindowHandle: ctrl for ctrl in win_controls if ctrl.NativeWindowHandle}
        handles = handles if handles is not None else list(handle_map.keys())
        monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: handles)
        monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
        monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: handle_map[handle])
        monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
        monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)
        return handle_map

    return _patch


# ---------------- A: get_similar_path 泛化逻辑 ----------------


class TestGetSimilarPath:
    def _strategy_svc(self, old_ele):
        return SimpleNamespace(data={"data": old_ele, "pick_type": "SIMILAR"})

    def test_跨窗口标题_根层禁用name并标记共同父级(self):
        path1 = [
            _node("WindowControl", cls="AppWin", name="Doc1"),
            _node("PaneControl", cls="PaneCtl", name="Main"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path2 = [
            _node("WindowControl", cls="AppWin", name="Doc2"),
            _node("PaneControl", cls="PaneCtl", name="Main"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        old = {"app": "app", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(self._strategy_svc(old), {"app": "app", "type": "uia", "path": path2})
        assert res is path1
        assert "name" in res[0]["disable_keys"]
        assert res[0]["similar_parent"] is True
        assert res[1]["similar_parent"] is True
        assert res[2]["disable_keys"] == ["cls", "name", "value", "index"]  # 首个区分层仅tag
        assert not res[2].get("similar_parent")

    def test_同窗口_根层不禁用name(self):
        path1 = [
            _node("WindowControl", cls="AppWin", name="Doc1"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path2 = [
            _node("WindowControl", cls="AppWin", name="Doc1"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        old = {"app": "app", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(self._strategy_svc(old), {"app": "app", "type": "uia", "path": path2})
        assert res is not None
        assert "name" not in res[0]["disable_keys"]

    def test_完全相同路径_返回None(self):
        path1 = [_node("WindowControl", cls="W", name="D"), _node("ListItemControl", cls="LI", name="A")]
        old = {"app": "app", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(
            self._strategy_svc(old),
            {
                "app": "app",
                "type": "uia",
                "path": [_node("WindowControl", cls="W", name="D"), _node("ListItemControl", cls="LI", name="A")],
            },
        )
        assert res is None

    def test_祖先关系_返回None(self):
        path1 = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListItemControl", cls="LI", name="A"),
        ]
        path2 = [_node("WindowControl", cls="W", name="D"), _node("PaneControl", cls="P", name="M")]
        old = {"app": "app", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(self._strategy_svc(old), {"app": "app", "type": "uia", "path": path2})
        assert res is None

    def test_不同应用_返回None(self):
        path1 = [_node("WindowControl", cls="W", name="D"), _node("ListItemControl", cls="LI", name="A", index=0)]
        path2 = [_node("WindowControl", cls="W", name="D"), _node("ListItemControl", cls="LI", name="B", index=1)]
        old = {"app": "app1", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(self._strategy_svc(old), {"app": "app2", "type": "uia", "path": path2})
        assert res is None

    def test_深度不同_长路径尾部层全部标记区分层(self):
        path1 = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListItemControl", cls="LI", name="A", index=0),
            _node("TextControl", cls="T", name="A", index=0),
        ]
        path2 = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        old = {"app": "app", "type": "uia", "path": path1}
        res = UIAPicker.get_similar_path(self._strategy_svc(old), {"app": "app", "type": "uia", "path": path2})
        assert res is not None
        assert res[2]["disable_keys"] == ["cls", "name", "value", "index"]
        assert res[3]["disable_keys"] == ["name", "value"]  # 后续区分层禁name/value


# ---------------- B: 窗口搜索 None 过滤 ----------------


class TestWindowSearchNoneFilter:
    def _patch_handles(self, monkeypatch, windows):
        ctrls = {h: SimpleNamespace(Name=name, ClassName=cls) for h, (cls, name) in windows.items()}
        monkeypatch.setattr(locator_window_mod, "find_app_handles", lambda app: list(windows.keys()))
        monkeypatch.setattr(locator_window_mod, "ControlFromHandle", lambda h: ctrls[h])
        return ctrls

    def test_name为None_不应过滤掉全部窗口(self, monkeypatch):
        self._patch_handles(monkeypatch, {1001: ("AppWin", "Doc1"), 1002: ("AppWin", "Doc2")})
        res = locator_window_mod.find_window_handles_list("AppWin", None, app_name="app")
        assert set(res) == {1001, 1002}

    def test_name为None_返回全部实例而非仅同名(self, monkeypatch):
        self._patch_handles(monkeypatch, {1001: ("AppWin", "Doc1"), 1002: ("AppWin", "Doc2")})
        res = locator_window_mod.find_window_by_enum_list("AppWin", None, app_name="app")
        assert set(res) == {1001, 1002}

    def test_name指定_保持同名精确匹配(self, monkeypatch):
        self._patch_handles(monkeypatch, {1001: ("AppWin", "Doc1"), 1002: ("AppWin", "Doc2")})
        res = locator_window_mod.find_window_handles_list("AppWin", "Doc1", app_name="app")
        assert res == [1001]

    def test_cls为None_不按类名过滤(self, monkeypatch):
        self._patch_handles(monkeypatch, {1001: ("AppWin", "Doc1"), 1002: ("OtherCls", "Doc1")})
        res = locator_window_mod.find_window_handles_list(None, "Doc1", app_name="app")
        assert set(res) == {1001, 1002}


# ---------------- C: __find_similar__ / __find_one__ ----------------


class TestFindSimilar:
    def test_正常场景_父路径全命中返回全部相似项(self, patch_locator_env):
        win, pane, list_ctrl = _build_tree()
        patch_locator_env([win])
        res = uia_mod.UIAFactory.find(_similar_ele(), "SIMILAR")
        assert isinstance(res, list)
        assert [loc.control().Name for loc in res] == ["A", "B", "C"]

    def test_父路径中间层动态变化_截短后仍能匹配(self, patch_locator_env):
        # List 的 name 在拾取后变化(如选中态/页码), 全路径强匹配必失败
        win, pane, list_ctrl = _build_tree(list_name="任务列表-第2页")
        patch_locator_env([win])
        res = uia_mod.UIAFactory.find(_similar_ele(), "SIMILAR")
        assert isinstance(res, list)
        assert len(res) == 3  # 截掉List层后, List作为结构层(tag+cls)继续匹配

    def test_父路径全部失效_降级到窗口层兜底(self, patch_locator_env):
        # Pane 与 List 均动态变化, 父路径截短到仅剩窗口层
        win, pane, list_ctrl = _build_tree(pane_name="Main-已切换", list_name="任务列表-第2页")
        patch_locator_env([win])
        res = uia_mod.UIAFactory.find(_similar_ele(), "SIMILAR")
        assert isinstance(res, list)
        assert len(res) == 3  # 从窗口层向下经结构层(Pane/List)逐层匹配

    def test_多窗口实例_遍历句柄找到可匹配实例(self, patch_locator_env):
        win1, _, _ = _build_tree()
        # 第二个实例: Pane name 不同, 首个句柄匹配失败后应继续尝试
        other_list = FakeControl(
            "ListControl",
            cls="ListCtl",
            name="任务列表",
            children=[FakeControl("ListItemControl", cls="ListItemCtl", name="X")],
        )
        other_pane = FakeControl("PaneControl", cls="PaneCtl", name="Other", children=[other_list])
        win2 = FakeControl("WindowControl", cls="AppWin", name="Doc2", children=[other_pane], handle=1002)
        patch_locator_env([win2, win1], handles=[1002, 1001])
        res = uia_mod.UIAFactory.find(_similar_ele(), "SIMILAR")
        assert isinstance(res, list)
        assert [loc.control().Name for loc in res] == ["A", "B", "C"]


class TestFindOneSingleLayer:
    def test_单层路径_返回窗口控件(self, patch_locator_env):
        win, _, _ = _build_tree()
        patch_locator_env([win])
        ele = {
            "app": "app",
            "type": "uia",
            "path": [_node("WindowControl", cls="AppWin", name="Doc1")],
        }
        res = uia_mod.UIAFactory.__find_one__(ele, "SIMILAR")
        assert res is not None
        assert res.control() is win

    def test_多层路径_行为不变(self, patch_locator_env):
        win, pane, _ = _build_tree()
        patch_locator_env([win])
        ele = {
            "app": "app",
            "type": "uia",
            "path": [
                _node("WindowControl", cls="AppWin", name="Doc1"),
                _node("PaneControl", cls="PaneCtl", name="Main"),
            ],
        }
        res = uia_mod.UIAFactory.__find_one__(ele, "ELEMENT")
        assert res is not None
        assert res.control() is pane
