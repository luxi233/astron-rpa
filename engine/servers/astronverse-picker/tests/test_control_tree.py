"""E1 控件树导出回归测试。

覆盖:
1. dump_control_tree 树形结构/属性序列化
2. 深度上限截断与 None 根控件报错
3. 属性访问异常的控件安全降级
4. ws 命令 CONTROL_TREE 路由与响应结构
"""

import json
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

from astronverse.picker import PickerSign
from astronverse.picker.core.control_tree import dump_control_tree
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire

from test_ws_server import _FakeSvc, _run, fake_ui  # noqa: E402, F401


class TreeControl:
    """带 GetChildren 的树形控件桩"""

    def __init__(self, tag, cls="", name="", automation_id=None, children=None, broken_attr=False):
        self.ControlTypeName = tag
        self.ClassName = cls
        self.Name = name
        if automation_id is not None:
            self.AutomationId = automation_id
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=10, bottom=10)
        self._children = children or []
        self._broken_attr = broken_attr

    def GetChildren(self):
        return self._children


def _sample_tree():
    btn = TreeControl("ButtonControl", cls="Btn", name="确定", automation_id="okBtn")
    edit = TreeControl("EditControl", cls="Edit", name="")
    pane = TreeControl("PaneControl", cls="Pane", name="主面板", children=[btn, edit])
    return TreeControl("WindowControl", cls="AppWin", name="Doc1", children=[pane]), pane, btn


def test_dump_树结构与属性序列化():
    win, pane, btn = _sample_tree()
    tree = dump_control_tree(win, max_depth=6)
    assert tree["tag_name"] == "WindowControl"
    assert tree["name"] == "Doc1"
    assert len(tree["children"]) == 1
    pane_node = tree["children"][0]
    assert pane_node["tag_name"] == "PaneControl"
    btn_node = pane_node["children"][0]
    assert btn_node["automation_id"] == "okBtn"
    assert btn_node["rect"] == {"left": 0, "top": 0, "right": 10, "bottom": 10}


def test_dump_深度上限截断():
    win, pane, btn = _sample_tree()
    tree = dump_control_tree(win, max_depth=2)
    assert tree["children"][0]["tag_name"] == "PaneControl"
    assert tree["children"][0]["children"] == []  # 第3层被截断


def test_dump_空name与缺失automation_id归一None():
    win, pane, btn = _sample_tree()
    tree = dump_control_tree(win, max_depth=6)
    edit_node = tree["children"][0]["children"][1]
    assert edit_node["name"] is None
    assert edit_node["automation_id"] is None


def test_dump_属性异常安全降级():
    class Broken:
        @property
        def ControlTypeName(self):
            raise OSError("control vanished")

        def GetChildren(self):
            raise OSError("control vanished")

    tree = dump_control_tree(Broken(), max_depth=3)
    assert tree["tag_name"] is None
    assert tree["children"] == []


def test_dump_None根控件报错():
    with pytest.raises(Exception, match="未获取到根控件"):
        dump_control_tree(None)


# ---------------- WS 命令路由 ----------------


def test_ws_CONTROL_TREE导出成功(monkeypatch):
    win, _, _ = _sample_tree()
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "GetRootControl", lambda: win, raising=False)
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.CONTROL_TREE, ext_data={"max_depth": 4})
    result = _run(handler._handle_control_tree(req))
    assert result["success"] is True
    tree = json.loads(result["data"])
    assert tree["tag_name"] == "WindowControl"


def test_ws_CONTROL_TREE指定句柄(monkeypatch):
    win, _, _ = _sample_tree()
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ControlFromHandle", lambda handle: win, raising=False)
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.CONTROL_TREE, ext_data={"handle": 1001, "max_depth": 2})
    result = _run(handler._handle_control_tree(req))
    assert result["success"] is True


def test_ws_CONTROL_TREE无根控件返回错误(monkeypatch):
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "GetRootControl", lambda: None, raising=False)
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.CONTROL_TREE)
    result = _run(handler._handle_control_tree(req))
    assert result["success"] is False


def test_ws_CONTROL_TREE节点rect高亮(fake_ui, monkeypatch):
    """ext_data.rect 存在时不导出树, 仅按 rect 绘制高亮"""
    monkeypatch.setattr("astronverse.picker.server.ws_server.time", mock.MagicMock())
    drawn = []
    fake_ui["highlight"].draw_wnd = lambda rects, *a: drawn.append(rects)
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(
        pick_sign=PickerSign.CONTROL_TREE,
        ext_data={"rect": {"left": 1, "top": 2, "right": 11, "bottom": 12}},
    )
    result = _run(handler._handle_control_tree(req))
    assert result == {"success": True, "data": ""}
    assert len(drawn) == 1
    assert (drawn[0].left, drawn[0].top, drawn[0].right, drawn[0].bottom) == (1, 2, 11, 12)
