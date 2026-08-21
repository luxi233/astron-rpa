"""深度捕获实时控件树(I5)回归测试。

覆盖:
1. dump_live_tree 祖先链/focused 标记/兄弟窗口裁剪/焦点子树展开/节点上限截断
2. PickerCore._push_live_tree 指纹去重/150ms 节流/通道未注册跳过/异常不阻断
3. ws 路由: DeepUIA START 注册推送通道并清理; 推送泵以 PICK_TREE_UPDATE 发送
"""

import asyncio
import itertools
import json
import queue
import time
from types import SimpleNamespace

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_capture_mode as _cm  # noqa: F401
from astronverse.picker import PickerSign, PickerType  # noqa: E402
from astronverse.picker.core.control_tree import dump_live_tree  # noqa: E402
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire, PushKey  # noqa: E402

from test_ws_server import _FakeSvc, _FakeWS, _run, fake_ui  # noqa: E402, F401

_rid_seq = itertools.count(1)


class LiveControl:
    """带父子双向遍历与 RuntimeId 的控件桩"""

    def __init__(self, tag, name="", children=None):
        self.ControlTypeName = tag
        self.ClassName = ""
        self.Name = name
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=10, bottom=10)
        self._rid = (next(_rid_seq),)
        self._parent = None
        self._children = children or []
        for c in self._children:
            c._parent = self

    def GetChildren(self):
        return self._children

    def GetParent(self):
        return self._parent

    def GetRuntimeId(self):
        return self._rid


def _chain():
    """窗口 -> 面板 -> 按钮, 返回 (win, pane, btn)。自底向上构造避免覆盖已建立的父引用"""
    btn = LiveControl("ButtonControl", name="确定")
    pane = LiveControl("PaneControl", name="主面板")
    pane._children.append(btn)
    btn._parent = pane
    win = LiveControl("WindowControl", name="Doc1")
    win._children.append(pane)
    pane._parent = win
    return win, pane, btn


# ---------------- dump_live_tree ----------------


def test_live树_祖先链完整且聚焦标记正确():
    _, _, btn = _chain()
    tree = dump_live_tree(btn)
    assert tree["tag_name"] == "WindowControl"
    assert tree["focused"] is False
    pane_node = tree["children"][0]
    assert pane_node["tag_name"] == "PaneControl" and pane_node["focused"] is False
    btn_node = pane_node["children"][0]
    assert btn_node["tag_name"] == "ButtonControl" and btn_node["focused"] is True
    assert tree["truncated"] is False


def test_live树_兄弟窗口裁剪():
    children = [LiveControl("ButtonControl", name=f"b{i}") for i in range(9)]
    pane = LiveControl("PaneControl")
    pane._children = children
    for c in children:
        c._parent = pane
    win = LiveControl("WindowControl")  # noqa: F841
    win._children.append(pane)
    pane._parent = win
    focus = children[4]
    tree = dump_live_tree(focus, sibling_span=2)
    names = [c["name"] for c in tree["children"][0]["children"]]
    # 聚焦项 b4 前后各 2 个兄弟
    assert names == ["b2", "b3", "b4", "b5", "b6"]
    assert next(c for c in tree["children"][0]["children"] if c["name"] == "b4")["focused"] is True


def test_live树_焦点子树展开():
    grand = LiveControl("TextControl", name="孙")
    c1 = LiveControl("TextControl", name="子1")
    c1._children.append(grand)
    grand._parent = c1
    c2 = LiveControl("TextControl", name="子2")
    btn = LiveControl("ButtonControl", name="确定")
    btn._children.extend([c1, c2])
    c1._parent = btn
    c2._parent = btn
    pane = LiveControl("PaneControl")
    pane._children.append(btn)
    btn._parent = pane
    tree = dump_live_tree(btn)
    # 根为 pane(祖先链 pane -> btn), 聚焦节点展开 2 层子树
    btn_node = tree["children"][0]
    assert btn_node["focused"] is True
    assert [c["name"] for c in btn_node["children"]] == ["子1", "子2"]
    assert btn_node["children"][0]["children"][0]["name"] == "孙"


def test_live树_节点上限截断():
    children = [LiveControl("ButtonControl", name=f"b{i}") for i in range(350)]
    btn = LiveControl("PaneControl")
    btn._children = children
    for c in children:
        c._parent = btn
    tree = dump_live_tree(btn)
    assert tree["truncated"] is True
    assert len(tree["children"]) < 350


def test_live树_None控件报错():
    with pytest.raises(Exception, match="未获取到焦点控件"):
        dump_live_tree(None)


# ---------------- PickerCore._push_live_tree ----------------


class _LiveEle:
    """带 control 引用的假元素"""

    def __init__(self, control, rect=(0, 0, 10, 10)):
        self.control = control
        self._rect = rect

    def rect(self):
        return SimpleNamespace(left=self._rect[0], top=self._rect[1], right=self._rect[2], bottom=self._rect[3])


def _core():
    from astronverse.picker.core import picker_core_win as pcw

    return pcw.PickerCore()


def test_push_深度会话入队且payload含聚焦节点():
    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 1
    payload = json.loads(q.get_nowait())
    assert payload["tag_name"] == "WindowControl"
    assert payload["children"][0]["children"][0]["focused"] is True


def test_push_指纹去重不重推():
    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    core._live_tree_last_ts -= 1  # 排除节流影响, 仅验证去重
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 1


def test_push_节流150ms内跳过():
    _, pane, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 1
    # 焦点变了但距上次推送不足 150ms -> 跳过
    core._push_live_tree(svc, _LiveEle(pane))
    assert q.qsize() == 1
    # 时间窗口过后 -> 推送新焦点
    core._live_tree_last_ts = time.time() - 0.2
    core._push_live_tree(svc, _LiveEle(pane))
    assert q.qsize() == 2


def test_push_通道未注册静默跳过():
    _, _, btn = _chain()
    core = _core()
    # 无 deep_tree_queue/deep_tree_ws(非深度会话)
    core._push_live_tree(SimpleNamespace(), _LiveEle(btn))
    # 队列满时丢弃不阻塞
    q = queue.Queue(maxsize=1)
    q.put("old")
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.get_nowait() == "old"


def test_push_构树异常不阻断(monkeypatch):
    from astronverse.picker.core import control_tree as ct

    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core = _core()
    monkeypatch.setattr(ct, "dump_live_tree", lambda c: (_ for _ in ()).throw(OSError("control vanished")))
    core._push_live_tree(svc, _LiveEle(btn))  # 不抛异常
    assert q.qsize() == 0


# ---------------- ws 路由与推送泵 ----------------


def _start_req(**kw):
    return PickerRequire(pick_sign=PickerSign.START, pick_type=PickerType.ELEMENT, **kw)


def test_deep_START注册推送通道且会话后清理(fake_ui):
    captured = {}

    def probe(sign, data):
        captured["ws"] = svc.deep_tree_ws
        captured["queue"] = svc.deep_tree_queue
        return {"ok": 1}

    svc = _FakeSvc(sign_result=probe)
    handler = PickerRequestHandler(svc)
    ws = _FakeWS()
    result = _run(handler._handle_pick_start(ws, _start_req(pick_mode="DeepUIA")))
    assert result["success"] is True
    # send_sign 挂起期间通道已注册
    assert captured["ws"] is ws and captured["queue"] is not None
    # 会话结束后清理
    assert svc.deep_tree_ws is None and svc.deep_tree_queue is None


def test_非deep_START不注册通道(fake_ui):
    captured = {}

    def probe(sign, data):
        captured["ws"] = getattr(svc, "deep_tree_ws", None)
        return {"ok": 1}

    svc = _FakeSvc(sign_result=probe)
    handler = PickerRequestHandler(svc)
    _run(handler._handle_pick_start(_FakeWS(), _start_req()))
    assert captured["ws"] is None


def test_推送泵以PICK_TREE_UPDATE发送():
    async def scenario():
        svc = _FakeSvc()
        handler = PickerRequestHandler(svc)
        ws = _FakeWS()
        q = queue.Queue()
        svc.deep_tree_ws = ws
        svc.deep_tree_queue = q
        q.put('{"focused": true}')
        task = asyncio.create_task(handler._deep_tree_pump(ws, q))
        await asyncio.sleep(0.2)
        svc.deep_tree_ws = None  # 摘除通道让泵退出
        await asyncio.wait_for(task, timeout=2)
        return ws.sent

    sent = asyncio.run(scenario())
    assert len(sent) == 1
    msg = json.loads(sent[0])
    assert msg["key"] == PushKey.PICK_TREE_UPDATE.value
    assert msg["message_type"] == "push"
    assert msg["data"] == '{"focused": true}'


def test_推送泵发送异常即退出():
    class _BrokenWS:
        def __init__(self):
            self.count = 0

        async def send(self, msg):
            self.count += 1
            raise ConnectionError("closed")

    async def scenario():
        svc = _FakeSvc()
        handler = PickerRequestHandler(svc)
        ws = _BrokenWS()
        q = queue.Queue()
        svc.deep_tree_ws = ws
        svc.deep_tree_queue = q
        q.put("x")
        task = asyncio.create_task(handler._deep_tree_pump(ws, q))
        await asyncio.wait_for(task, timeout=2)
        return ws.count

    assert asyncio.run(scenario()) == 1  # 首次发送失败即退出, 不死循环
