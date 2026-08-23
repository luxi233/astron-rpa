"""深度捕获全窗口树与属性面板回归测试(对齐影刀形态)。

覆盖:
1. dump_live_tree 根层(桌面)全量列出所有顶层窗口 + 根节点 root 标记
2. dump_desktop_tree 首帧桌面树(全窗口单层)/节点上限截断
3. dump_control_props UIA 属性导出(含 False 布尔保留/进程名/BoundingRectangle)
4. deep START 首帧桌面树入队; TREE_PROPS 属性查询(定位成功/失败一律 success 不结束会话)
5. websocket_endpoint 深度 START 并发化: 会话挂起期间 TREE_PROPS 仍被处理
"""

import asyncio
import json
import queue
import sys
import types
from types import SimpleNamespace

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_capture_mode as _cm  # noqa: F401
from astronverse.picker import PickerSign, PickerType
from astronverse.picker.core.control_tree import dump_control_props, dump_desktop_tree, dump_live_tree
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire, WsServer
from test_live_tree import LiveControl, _chain
from test_ws_server import _FakeSvc, _FakeWS, _make_mod, _run, fake_ui  # noqa: E402, F401


def _start_req(**kw):
    return PickerRequire(pick_sign=PickerSign.START, pick_type=PickerType.ELEMENT, **kw)


# ---------------- dump_live_tree 根层全量与 root 标记 ----------------


def test_live树_根层全量列出所有顶层窗口():
    """根层(运行时为桌面)不裁剪: 9 个顶层窗口全量展示, 裁剪只作用于窗口以下的聚焦链层"""
    wins = [LiveControl("WindowControl", name=f"w{i}") for i in range(9)]
    desktop = LiveControl("PaneControl", name="Desktop")
    desktop._children = wins
    for w in wins:
        w._parent = desktop
    btn = LiveControl("ButtonControl", name="btn")
    wins[4]._children.append(btn)
    btn._parent = wins[4]
    tree = dump_live_tree(btn, sibling_span=2)
    assert tree["root"] is True
    assert [c["name"] for c in tree["children"]] == [f"w{i}" for i in range(9)]
    # 窗口内聚焦链层仍按 sibling_span 裁剪
    win_node = tree["children"][4]
    assert [c["name"] for c in win_node["children"]] == ["btn"]


def test_live树_根标记只附在根节点():
    _, _, btn = _chain()
    tree = dump_live_tree(btn)
    assert tree["root"] is True
    assert "root" not in tree["children"][0]
    assert "root" not in tree["children"][0]["children"][0]


# ---------------- dump_desktop_tree 首帧桌面树 ----------------


def test_desktop树_全窗口单层结构():
    wins = [LiveControl("WindowControl", name=f"w{i}") for i in range(3)]
    desktop = LiveControl("PaneControl", name="Desktop")
    desktop._children = wins
    for w in wins:
        w._parent = desktop
    tree = dump_desktop_tree(root=desktop)
    assert tree["root"] is True
    assert tree["truncated"] is False
    assert tree["tag_name"] == "PaneControl"
    assert [c["name"] for c in tree["children"]] == ["w0", "w1", "w2"]
    # 顶层窗口不展开(单层, 鼠标聚焦后由实时树展开祖先链)
    assert all(not c["children"] for c in tree["children"])
    assert all("root" not in c for c in tree["children"])


def test_desktop树_节点上限截断():
    wins = [LiveControl("WindowControl", name=f"w{i}") for i in range(600)]
    desktop = LiveControl("PaneControl")
    desktop._children = wins
    for w in wins:
        w._parent = desktop
    tree = dump_desktop_tree(root=desktop)
    assert tree["truncated"] is True
    assert len(tree["children"]) < 600


# ---------------- dump_control_props 属性面板 ----------------


def _props_control():
    return SimpleNamespace(
        ControlTypeName="ButtonControl",
        LocalizedControlType="按钮",
        Name="确定",
        ClassName="Button",
        AutomationId="okBtn",
        FrameworkId="Win32",
        IsEnabled=False,  # False 是有意义值, 不得被 falsy 丢弃
        IsOffscreen=True,
        HelpText="提交表单",
        ProcessId="1234",
        GetRuntimeId=lambda: (42, 7),
        BoundingRectangle=SimpleNamespace(left=1, top=2, right=11, bottom=12),
    )


def test_属性导出_完整键值与False保留(monkeypatch):
    from astronverse.picker.utils import process as proc_mod

    monkeypatch.setattr(proc_mod, "find_real_application_process", lambda pid: {"name": "notepad"})
    props = dump_control_props(_props_control())
    assert props["ControlTypeName"] == "ButtonControl"
    assert props["Name"] == "确定"
    assert props["AutomationId"] == "okBtn"
    assert props["IsEnabled"] == "False"
    assert props["IsOffscreen"] == "True"
    assert props["ProcessId"] == "1234"
    assert props["ProcessName"] == "notepad"
    assert props["RuntimeId"] == "42-7"
    assert props["BoundingRectangle"] == "(1, 2) - (11, 12)"


def test_属性导出_进程查询失败不影响其余属性(monkeypatch):
    from astronverse.picker.utils import process as proc_mod

    def _boom(pid):
        raise OSError("gone")

    monkeypatch.setattr(proc_mod, "find_real_application_process", _boom)
    props = dump_control_props(_props_control())
    assert props["ProcessId"] == "1234"
    assert "ProcessName" not in props
    assert props["Name"] == "确定"


def test_属性导出_缺属性跳过不抛错():
    props = dump_control_props(SimpleNamespace(ControlTypeName="PaneControl", GetRuntimeId=lambda: (1,)))
    assert props == {"ControlTypeName": "PaneControl", "RuntimeId": "1"}


# ---------------- ws 首帧桌面树 ----------------


def test_deep_START首帧桌面树直发(fake_ui, monkeypatch):
    """深度会话注册通道即直发桌面全窗口首帧(PICK_TREE_UPDATE push), 不必等鼠标移动到目标应用"""
    from astronverse.picker.core import control_tree as ct
    from astronverse.picker.server.ws_server import PushKey

    monkeypatch.setattr(ct, "dump_desktop_tree", lambda: {"tag_name": "PaneControl", "root": True, "children": []})

    svc = _FakeSvc(sign_result=lambda sign, data: {"ok": 1})
    handler = PickerRequestHandler(svc)
    ws = _FakeWS()
    result = _run(handler._handle_pick_start(ws, _start_req(pick_mode="DeepUIA")))
    assert result["success"] is True
    pushes = [json.loads(m) for m in ws.sent if json.loads(m).get("message_type") == "push"]
    assert len(pushes) == 1
    assert pushes[0]["key"] == PushKey.PICK_TREE_UPDATE.value
    payload = json.loads(pushes[0]["data"])
    assert payload["tag_name"] == "PaneControl"
    assert payload["root"] is True


def test_非deep_START不推首帧(fake_ui):
    svc = _FakeSvc(sign_result=lambda sign, data: {"ok": 1})
    handler = PickerRequestHandler(svc)
    ws = _FakeWS()
    _run(handler._handle_pick_start(ws, _start_req()))
    # 队列已随会话清理为 None(从未注册), 且无任何 push 消息直发
    assert svc.deep_tree_queue is None
    assert all(json.loads(m).get("message_type") != "push" for m in ws.sent)


def test_首帧构树异常静默跳过(fake_ui, monkeypatch):
    """uiautomation 不可用/桌面枚举失败时首帧跳过, 不影响拾取主流程"""
    from astronverse.picker.core import control_tree as ct

    def _boom():
        raise OSError("no uia")

    monkeypatch.setattr(ct, "dump_desktop_tree", _boom)

    svc = _FakeSvc(sign_result=lambda sign, data: {"ok": 1})
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_pick_start(_FakeWS(), _start_req(pick_mode="DeepUIA")))
    assert result["success"] is True


# ---------------- TREE_PROPS 属性查询 ----------------


@pytest.fixture
def locator_stub(monkeypatch):
    """LocatorManager 桩: 按可编程返回值定位(必须 setitem 安装, 避免污染真实模块)"""
    state = {"element": None, "raise": None, "located": object()}
    stub_mod = types.ModuleType("astronverse.locator.locator")

    class _Manager:
        def locator(self, element, **kw):
            if state["raise"] is not None:
                raise state["raise"]
            return state["located"]

    stub_mod.LocatorManager = _Manager
    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", stub_mod)
    return state


def _props_req(chain):
    return PickerRequire(pick_sign=PickerSign.TREE_PROPS, pick_type=PickerType.ELEMENT, data=json.dumps(chain))


def test_TREE_PROPS_定位成功返回属性(fake_ui, locator_stub):
    located = SimpleNamespace(control=lambda: _props_control())
    locator_stub["located"] = located
    svc = _FakeSvc()
    handler = PickerRequestHandler(svc)
    result = _run(
        handler._handle_tree_props(
            _props_req([{"tag_name": "WindowControl", "name": "w"}, {"tag_name": "ButtonControl", "name": "确定"}])
        )
    )
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["tree_props"] is True
    assert payload["props"]["ControlTypeName"] == "ButtonControl"
    assert payload["props"]["IsEnabled"] == "False"


def test_TREE_PROPS_定位失败返回null且success(fake_ui, locator_stub):
    """定位失败不结束会话: success + props=null, 前端回退显示节点自带字段"""
    locator_stub["located"] = None
    svc = _FakeSvc()
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_tree_props(_props_req([{"tag_name": "WindowControl", "name": "w"}])))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["tree_props"] is True
    assert payload["props"] is None


def test_TREE_PROPS_定位异常也返回success(fake_ui, locator_stub):
    locator_stub["raise"] = OSError("com gone")
    svc = _FakeSvc()
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_tree_props(_props_req([{"tag_name": "WindowControl", "name": "w"}])))
    assert result["success"] is True
    assert json.loads(result["data"])["props"] is None


def test_TREE_PROPS_链空返回success(fake_ui):
    svc = _FakeSvc()
    handler = PickerRequestHandler(svc)
    result = _run(
        handler._handle_tree_props(
            PickerRequire(pick_sign=PickerSign.TREE_PROPS, pick_type=PickerType.ELEMENT, data="[]")
        )
    )
    assert result["success"] is True
    assert json.loads(result["data"])["props"] is None


def test_会话内查询信号不关闭连接(fake_ui, locator_stub):
    """H1 回归: handle_request 对 TREE_PROPS/TREE_PICK 返回 False(不关连接)。

    误关会拆毁整个深度捕获会话(连接生命周期由并发化的深度 START task 管理):
    首次单击树节点即触发前端 bindClose → finishPick, 面板关闭拾取失败。"""
    locator_stub["located"] = None
    handler = PickerRequestHandler(_FakeSvc())
    for sign in (PickerSign.TREE_PROPS, PickerSign.TREE_PICK):
        req = PickerRequire(
            pick_sign=sign, pick_type=PickerType.ELEMENT, data='[{"tag_name": "WindowControl", "name": "w"}]'
        )
        assert _run(handler.handle_request(_FakeWS(), req)) is False
    # 非会话内查询信号仍保持原有语义(处理完关连接)
    stop_req = PickerRequire(pick_sign=PickerSign.STOP, pick_type=PickerType.ELEMENT)
    assert _run(handler.handle_request(_FakeWS(), stop_req)) is True


# ---------------- websocket_endpoint 深度 START 并发化 ----------------


class _SeqWS:
    """按序消费预置消息的假 ws 连接(每次 recv 让出控制权, 模拟真实网络接收挂起,
    使并发 task 有机会被调度)"""

    def __init__(self, msgs):
        self._msgs = list(msgs)
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0)
        if not self._msgs:
            raise StopAsyncIteration
        return self._msgs.pop(0)

    async def send(self, msg):
        self.sent.append(msg)

    async def close(self):
        self.closed = True


def test_深度START挂起期间会话内请求仍被处理(fake_ui, locator_stub, monkeypatch):
    """回归: 深度 START 在主循环顺序 await 时, send_sign 挂起整个会话,
    TREE_PROPS/TREE_PICK 等会话内请求将永不被处理——并发化后主循环继续收消息"""
    from astronverse.picker.core import control_tree as ct

    monkeypatch.setattr(ct, "dump_desktop_tree", lambda: {"tag_name": "PaneControl", "root": True, "children": []})

    # recorder stub 需带 set_push_callbacks(WsServer 构造时安装推送回调)
    recorder = types.SimpleNamespace(set_push_callbacks=lambda **kw: None)
    monkeypatch.setitem(sys.modules, "astronverse.picker.core.recorder_core_win", _make_mod(record_manager=recorder))
    locator_stub["located"] = SimpleNamespace(control=lambda: _props_control())

    chain = [{"tag_name": "WindowControl", "name": "w"}, {"tag_name": "ButtonControl", "name": "确定"}]
    msgs = [
        json.dumps({"pick_sign": "START", "pick_type": "ELEMENT", "pick_mode": "DeepUIA"}),
        json.dumps({"pick_sign": "TREE_PROPS", "data": json.dumps(chain)}),
    ]
    ws = _SeqWS(msgs)
    tree_props_ack_seen = asyncio.Event()
    seen_during_pick = {}

    async def fake_send_sign(sign, data):
        # START 挂起中: 等 TREE_PROPS 的 ack 出现(仅并发化生效才可能在挂起期间到达), 最多 2s;
        # 直接覆盖 send_sign(_FakeSvc 的实现不 await 可编程结果, 无法挂起)
        try:
            await asyncio.wait_for(tree_props_ack_seen.wait(), timeout=2)
            seen_during_pick["during"] = True
        except asyncio.TimeoutError:
            seen_during_pick["during"] = False
        return {"ok": 1}

    svc = _FakeSvc()
    svc.send_sign = fake_send_sign
    server = WsServer(svc, 8001)

    async def scenario():
        # 单独消费 ws 消息流里的 tree_props ack: endpoint 主循环逐条处理
        await server.websocket_endpoint(ws)
        return [json.loads(m) for m in ws.sent]

    async def watcher():
        # 轮询 ack 到达并置事件, 供 START 的 probe 解除挂起
        for _ in range(100):
            for m in ws.sent:
                parsed = json.loads(m)
                if parsed.get("data"):
                    try:
                        if json.loads(parsed["data"]).get("tree_props"):
                            tree_props_ack_seen.set()
                            return
                    except (ValueError, TypeError):
                        continue
            await asyncio.sleep(0.02)

    async def run_both():
        await asyncio.gather(scenario(), watcher())
        # 消息流耗尽后 endpoint 退出(TREE_PROPS 不关连接, 连接随深度 START task 收尾);
        # 深度 START task 可能仍挂起, 等它跑完(probe 已被 watcher 置事件解除挂起, 最多再等 2s 兼容超时路径)
        for _ in range(100):
            if "during" in seen_during_pick:
                return
            await asyncio.sleep(0.02)

    asyncio.run(run_both())

    acks = []
    for m in ws.sent:
        parsed = json.loads(m)
        if parsed.get("data"):
            try:
                payload = json.loads(parsed["data"])
            except (ValueError, TypeError):
                continue
            if isinstance(payload, dict) and payload.get("tree_props"):
                acks.append(payload)
    # START 挂起期间 TREE_PROPS 已被处理并回 ack(顺序 await 回归时 ack 只会在 START 完成后出现, during=False)
    assert seen_during_pick["during"] is True
    assert len(acks) == 1
    assert acks[0]["props"]["ControlTypeName"] == "ButtonControl"
