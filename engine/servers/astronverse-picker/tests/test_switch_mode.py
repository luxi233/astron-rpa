"""I4 会话内捕获模式切换回归测试。

覆盖:
1. CaptureModeManager 状态机: 标准/深度/CV 互切, pick_mode 改写, requires_reinit 语义,
   残留清理, 非法模式拒绝, 切换历史留痕
2. WS SWITCH_MODE: 无活动会话报错 / 有活动会话就地改写会话字典并返回切换结果
"""

import json

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from test_ws_server import _run  # noqa: E402

from astronverse.picker import PickerSign  # noqa: E402
from astronverse.picker.core import capture_mode as cm  # noqa: E402
from astronverse.picker.core.capture_mode import CaptureMode, CaptureModeManager  # noqa: E402
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_singleton():
    """隔离模块级单例状态, 避免用例间 previous/history 串扰"""
    cm.capture_mode_manager.current = None
    cm.capture_mode_manager.history = []
    yield
    cm.capture_mode_manager.current = None
    cm.capture_mode_manager.history = []


# ---------------- 状态机 ----------------


class TestCaptureModeManager:
    def test_标准切深度写入DeepUIA(self):
        mgr = CaptureModeManager()
        data = {}
        res = mgr.switch(data, "deep")
        assert data["pick_mode"] == "DeepUIA"
        assert res["mode"] == "deep"
        assert res["requires_reinit"] is False

    def test_深度切标准移除pick_mode(self):
        mgr = CaptureModeManager()
        data = {"pick_mode": "DeepUIA"}
        res = mgr.switch(data, "standard")
        assert "pick_mode" not in data  # domain 回落 AUTO
        assert res["requires_reinit"] is False

    def test_切CV需重初始化(self):
        mgr = CaptureModeManager()
        data = {}
        res = mgr.switch(data, "cv")
        assert data["pick_mode"] == "CV"
        assert res["requires_reinit"] is True  # 独立 vision-picker 通道, 需退出重进

    def test_非法模式拒绝(self):
        mgr = CaptureModeManager()
        with pytest.raises(ValueError):
            mgr.switch({}, "not_a_mode")

    def test_残留deep标记被清理(self):
        mgr = CaptureModeManager()
        data = {"pick_mode": "DeepUIA", "deep": True}
        mgr.switch(data, "standard")
        assert "deep" not in data

    def test_切换历史与previous留痕(self):
        mgr = CaptureModeManager()
        data = {}
        r1 = mgr.switch(data, "deep")
        r2 = mgr.switch(data, "standard")
        assert r1["previous"] is None
        assert r2["previous"] == "deep"
        assert mgr.current == CaptureMode.STANDARD
        assert mgr.history == [(None, "deep"), ("deep", "standard")]

    def test_大小写归一化(self):
        mgr = CaptureModeManager()
        res = mgr.switch({}, "DEEP")
        assert res["mode"] == "deep"


# ---------------- WS SWITCH_MODE ----------------


class _ModeSvc:
    """伪 svc: sign() 返回可编程的会话信号映射(plain dict 即满足 in/getitem)"""

    def __init__(self, session=None):
        self._sign = {}
        if session is not None:
            self._sign[PickerSign.START.value] = session

    def sign(self):
        return self._sign


class TestWsSwitchMode:
    def test_无活动会话报错(self):
        handler = PickerRequestHandler(_ModeSvc(session=None))
        req = PickerRequire(pick_sign=PickerSign.SWITCH_MODE, data="deep")
        result = _run(handler._handle_switch_mode(req))
        assert result["success"] is False
        assert "无进行中的拾取会话" in result["error"]

    def test_有会话切换深度就地改写(self):
        session = {"pick_type": "ELEMENT", "pick_mode": ""}
        handler = PickerRequestHandler(_ModeSvc(session=session))
        req = PickerRequire(pick_sign=PickerSign.SWITCH_MODE, data="deep")
        result = _run(handler._handle_switch_mode(req))
        assert result["success"] is True
        payload = json.loads(result["data"])
        assert payload["mode"] == "deep"
        assert payload["requires_reinit"] is False
        # 会话字典被就地改写(绘制循环下一轮重读生效)
        assert session["pick_mode"] == "DeepUIA"

    def test_有会话切换CV标记重初始化(self):
        session = {"pick_type": "ELEMENT"}
        handler = PickerRequestHandler(_ModeSvc(session=session))
        req = PickerRequire(pick_sign=PickerSign.SWITCH_MODE, data="cv")
        result = _run(handler._handle_switch_mode(req))
        assert result["success"] is True
        payload = json.loads(result["data"])
        assert payload["requires_reinit"] is True

    def test_非法目标返回业务错误(self):
        session = {"pick_type": "ELEMENT"}
        handler = PickerRequestHandler(_ModeSvc(session=session))
        req = PickerRequire(pick_sign=PickerSign.SWITCH_MODE, data="invalid")
        result = _run(handler._handle_switch_mode(req))
        assert result["success"] is False
        assert "未知捕获模式" in result["error"]
