"""拾取器 ws 服务层单测: 消息模型/请求路由/三态响应/推送管理 (server/ws_server.py)"""

import asyncio
import json
import sys
import types
from unittest import mock

import pytest

from astronverse.picker import PickerSign, PickerType, RecordAction, SmartComponentAction
from astronverse.picker.server.ws_server import (
    MessageType,
    PickerMessage,
    PickerRequire,
    PickerRequestHandler,
    PushAcknowledgment,
    PushKey,
    PushManager,
    ResponseKey,
)


# ---------- 公共桩: 替换 Windows UI 依赖模块 ----------

class _FakeHighlight:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def start_wnd(self, *a, **k):
        pass

    def hide_wnd(self):
        pass

    def draw_wnd(self, *a, **k):
        pass


class _FakeOverlay:
    def show(self):
        pass

    def hide(self):
        pass


class _FakeRecorder:
    def __init__(self):
        self.calls = []

    async def handle_record_action(self, action, ws, svc, input_data):
        self.calls.append(action)
        return {"success": True, "data": ""}


def _make_mod(**attrs):
    mod = types.ModuleType("stub")
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


@pytest.fixture
def fake_ui(monkeypatch):
    """替换 highlight_client/block_overlay/recorder_core_win/locator 等延迟导入模块"""
    highlight = _FakeHighlight()
    overlay = _FakeOverlay()
    recorder = _FakeRecorder()

    fake_pkg = types.ModuleType("astronverse.picker.core")
    monkeypatch.setitem(sys.modules, "astronverse.picker.core.highlight_client",
                        _make_mod(highlight_client=highlight))
    monkeypatch.setitem(sys.modules, "astronverse.picker.core.block_overlay", _make_mod(block_overlay=overlay))
    monkeypatch.setitem(sys.modules, "astronverse.picker.core.recorder_core_win",
                        _make_mod(record_manager=recorder))
    return {"highlight": highlight, "overlay": overlay, "recorder": recorder}


class _FakeSvc:
    """伪 svc: tag/send_sign 可编程"""

    def __init__(self, sign_result=None):
        self.route_port = 8003
        self.sign_result = sign_result
        self.tags = []
        self.signs = []

    def tag(self, sign):
        self.tags.append(sign)

    async def send_sign(self, sign, data):
        self.signs.append((sign, data))
        result = self.sign_result
        if callable(result):
            return result(sign, data)
        return result


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestModels:
    def test_PickerRequire默认值(self):
        req = PickerRequire()
        assert req.pick_sign == PickerSign.START
        assert req.pick_type == PickerType.ELEMENT
        assert req.data is None and req.pick_mode is None

    def test_PickerRequire枚举解析(self):
        req = PickerRequire(pick_sign="HIGHLIGHT", pick_type="SIMILAR")
        assert req.pick_sign == PickerSign.HIGHLIGHT
        assert req.pick_type == PickerType.SIMILAR

    def test_create_response(self):
        m = PickerMessage.create_response(ResponseKey.SUCCESS, data="ok")
        assert m.key == "success"
        assert m.message_type is None  # 响应不带推送标记

    def test_create_push携带id与类型(self):
        m1 = PickerMessage.create_push(PushKey.RECORD_START, data="x")
        m2 = PickerMessage.create_push(PushKey.RECORD_START, data="x")
        assert m1.message_type == MessageType.PUSH.value
        assert m1.message_id and m1.message_id != m2.message_id
        assert m1.key == PushKey.RECORD_START.value

    def test_PushAcknowledgment模型(self):
        ack = PushAcknowledgment(reply_to="abc")
        assert ack.message_type == "ack" and ack.status == "success"


class TestHandleRequestRouting:
    def test_普通拾取后关闭连接(self, fake_ui):
        svc = _FakeSvc(sign_result={"e": 1})
        handler = PickerRequestHandler(svc)
        ws = _FakeWS()
        req = PickerRequire(pick_sign=PickerSign.STOP)
        closed = _run(handler.handle_request(ws, req))
        assert closed is True

    def test_录制请求不关闭连接(self, fake_ui):
        svc = _FakeSvc()
        handler = PickerRequestHandler(svc)
        req = PickerRequire(pick_sign=PickerSign.RECORD, record_action=RecordAction.START)
        closed = _run(handler.handle_request(_FakeWS(), req))
        assert closed is False
        assert fake_ui["recorder"].calls == [RecordAction.START]

    def test_智能组件请求不关闭连接(self, fake_ui):
        svc = _FakeSvc()
        handler = PickerRequestHandler(svc)
        req = PickerRequire(pick_sign=PickerSign.SMART_COMPONENT, smart_component_action=SmartComponentAction.END)
        closed = _run(handler.handle_request(_FakeWS(), req))
        assert closed is False


class TestPickStart:
    """_handle_pick_start 返回结果 dict, 由 _handle_picker_request 统一发送"""

    def _req(self, pick_type=PickerType.ELEMENT, **kw):
        return PickerRequire(pick_sign=PickerSign.START, pick_type=pick_type, **kw)

    def test_成功带picker_type(self, fake_ui):
        svc = _FakeSvc(sign_result={"element": "x"})
        handler = PickerRequestHandler(svc)
        result = _run(handler._handle_pick_start(self._req()))
        assert result["success"] is True
        assert result["data"]["picker_type"] == "ELEMENT"

    def test_取消(self, fake_ui):
        svc = _FakeSvc(sign_result="cancel")
        handler = PickerRequestHandler(svc)
        result = _run(handler._handle_pick_start(self._req()))
        assert result == {"success": False, "cancel": True}

    def test_字符串错误(self, fake_ui):
        svc = _FakeSvc(sign_result="拾取超时")
        handler = PickerRequestHandler(svc)
        result = _run(handler._handle_pick_start(self._req()))
        assert result == {"success": False, "error": "拾取超时"}

    def test_异常转错误响应(self, fake_ui):
        svc = _FakeSvc(sign_result=RuntimeError("boom"))
        handler = PickerRequestHandler(svc)
        result = _run(handler._handle_pick_start(self._req()))
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_SIMILAR触发元素数据预处理并注入pick_mode(self, fake_ui, monkeypatch):
        parsed = {"app": "chrome", "path": {"xpath": "//div"}}

        class _FakeLM:
            @staticmethod
            def parse_element_json(s):
                return parsed

        fake_locator_mod = _make_mod(LocatorManager=_FakeLM)
        monkeypatch.setitem(sys.modules, "astronverse.locator.locator", fake_locator_mod)

        svc = _FakeSvc(sign_result={"ok": 1})
        handler = PickerRequestHandler(svc)
        req = self._req(pick_type=PickerType.SIMILAR, data='{"raw": 1}', pick_mode="auto")
        _run(handler._handle_pick_start(req))
        # send_sign 收到的 data 里元素 JSON 已解析 + pick_mode 注入
        sign, payload = svc.signs[0]
        assert sign == PickerSign.START
        assert payload["data"]["app"] == "chrome"
        assert payload["data"]["pick_mode"] == "auto"


class TestPickStopValidateGainHighlight:
    def test_stop成功(self, fake_ui):
        handler = PickerRequestHandler(_FakeSvc())
        ws = _FakeWS()
        _run(handler._handle_pick_stop(PickerRequire(pick_sign=PickerSign.STOP)))
        _run(handler._send_response(ws, {"success": True}))
        assert json.loads(ws.sent[0])["key"] == "success"

    def test_validate单元素高亮(self, fake_ui, monkeypatch):
        from astronverse.picker import Rect

        class _Ele:
            def rect(self):
                return Rect(0, 0, 5, 5)

        class _FakeLM:
            def locator(self, data):
                return _Ele()

        monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))
        monkeypatch.setattr("astronverse.picker.server.ws_server.time", mock.MagicMock())
        handler = PickerRequestHandler(_FakeSvc())
        ws = _FakeWS()
        result = _run(handler._handle_pick_validate(PickerRequire(pick_sign=PickerSign.VALIDATE)))
        assert result == {"success": True, "data": "校验成功"}

    def test_validate异常返回错误(self, fake_ui, monkeypatch):
        class _FakeLM:
            @staticmethod
            def parse_element_json(s):
                return {}

            def locator(self, data):
                raise ValueError("元素定位失败")

        monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))
        handler = PickerRequestHandler(_FakeSvc())
        result = _run(handler._handle_pick_validate(PickerRequire(pick_sign=PickerSign.VALIDATE, data="bad")))
        assert result["success"] is False
        assert "元素定位失败" in result["error"]

    def test_gain批量数据走筛选(self, fake_ui, monkeypatch):
        element_data = {"app": "chrome", "path": {"produceType": "table", "values": [
            {"title": "名称", "value": ["a", "b"]}, {"title": "x", "value": ["1", "2"]},
        ]}}

        class _FakeLM:
            @staticmethod
            def parse_element_json(s):
                return element_data

        web_values = [{"value": ["a", "b"]}, {"value": ["1", "2"]}]

        from astronverse.picker.server import ws_server as ws_mod

        monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))
        monkeypatch.setattr(
            ws_mod.Browser, "send_browser_extension", mock.MagicMock(return_value={"values": web_values})
        )
        handler = PickerRequestHandler(_FakeSvc())
        ws = _FakeWS()
        _run(handler._handle_pick_gain(PickerRequire(pick_sign=PickerSign.GAIN, data='{"raw":1}')))
        _run(handler._send_response(ws, {"success": True, "data": {"values": []}}))
        assert json.loads(ws.sent[0])["key"] == "success"

    def test_highlight调用插件高亮(self, fake_ui, monkeypatch):
        from astronverse.picker.server import ws_server as ws_mod

        element_data = {"app": "chrome", "path": {"xpath": "//li"}}

        class _FakeLM:
            @staticmethod
            def parse_element_json(s):
                return element_data

        monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))
        called = mock.MagicMock()
        monkeypatch.setattr(ws_mod.Browser, "send_browser_extension", called)
        handler = PickerRequestHandler(_FakeSvc())
        _run(handler._handle_pick_highlight(PickerRequire(pick_sign=PickerSign.HIGHLIGHT, data='{"raw":1}')))
        assert called.call_count == 1
        assert called.call_args.kwargs["browser_type"] == "chrome"


class TestSendResponse:
    def _handler(self):
        return PickerRequestHandler(_FakeSvc())

    def test_success_dict转json字符串(self):
        ws = _FakeWS()
        _run(self._handler()._send_response(ws, {"success": True, "data": {"a": 1}}))
        assert json.loads(ws.sent[0])["data"] == '{"a": 1}'

    def test_success_非字符串强转str(self):
        ws = _FakeWS()
        _run(self._handler()._send_response(ws, {"success": True, "data": 123}))
        assert json.loads(ws.sent[0])["data"] == "123"

    def test_error默认消息(self):
        ws = _FakeWS()
        _run(self._handler()._send_response(ws, {"success": False}))
        resp = json.loads(ws.sent[-1])
        assert resp["key"] == "error" and resp["err_msg"] == "未知错误"

    def test_cancel先发cancel再发error兜底(self):
        """实现现状: cancel 响应后仍发送一条 error 兜底消息, 前端按 key 分流"""
        ws = _FakeWS()
        _run(self._handler()._send_response(ws, {"success": False, "cancel": True}))
        assert [json.loads(m)["key"] for m in ws.sent] == ["cancel", "error"]


class TestPushManager:
    def test_推送登记与确认(self):
        mgr = PushManager()
        ws = _FakeWS()
        mid = _run(mgr.send_push_message(ws, PushKey.RECORD_START, data="go"))
        assert mid in mgr.pending_pushes
        sent = json.loads(ws.sent[0])
        assert sent["message_id"] == mid and sent["key"] == "record_start"
        assert _run(mgr.handle_acknowledgment(PushAcknowledgment(reply_to=mid, status="success")))
        assert mid not in mgr.pending_pushes

    def test_确认未知id返回False(self):
        mgr = PushManager()
        assert _run(mgr.handle_acknowledgment(PushAcknowledgment(reply_to="nope"))) is False
