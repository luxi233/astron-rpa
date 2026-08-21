"""E5 行为校验回归测试。

覆盖:
1. 可点击/可输入/可悬停能力检查(禁用/屏幕外/无效区域/无输入Pattern)
2. UIA 布尔属性 property/method 两种形态兼容
3. ws VALIDATE 携带 validate_mode 的集成行为
"""

import sys
from types import SimpleNamespace
from unittest import mock

import pytest

from astronverse.picker import PickerSign, Rect
from astronverse.picker.core import behavior_check as bc
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire

from test_ws_server import _FakeSvc, _make_mod, _run, fake_ui  # noqa: E402


class BehaviorControl:
    """行为校验控件桩"""

    def __init__(self, enabled=True, offscreen=False, rect=(0, 0, 10, 10), value_pattern=True, bool_as_method=False):
        if bool_as_method:
            self.IsEnabled = lambda: enabled
            self.IsOffscreen = lambda: offscreen
        else:
            self.IsEnabled = enabled
            self.IsOffscreen = offscreen
        r = rect
        self.BoundingRectangle = SimpleNamespace(left=r[0], top=r[1], right=r[2], bottom=r[3])
        self._value_pattern = value_pattern

    def GetValuePattern(self):
        if not self._value_pattern:
            raise NotImplementedError("no value pattern")
        return SimpleNamespace(Value="")

    def GetTextPattern(self):
        raise NotImplementedError("no text pattern")


# ---------------- 能力检查 ----------------


def test_clickable_正常通过():
    ok, reason = bc.check_clickable(BehaviorControl())
    assert ok and reason == "元素可点击"


def test_clickable_禁用拒绝():
    ok, reason = bc.check_clickable(BehaviorControl(enabled=False))
    assert not ok and "禁用" in reason


def test_clickable_屏幕外拒绝():
    ok, reason = bc.check_clickable(BehaviorControl(offscreen=True))
    assert not ok and "屏幕外" in reason


def test_clickable_无效区域拒绝():
    ok, reason = bc.check_clickable(BehaviorControl(rect=(0, 0, 0, 0)))
    assert not ok and "区域无效" in reason


def test_inputable_支持ValuePattern通过():
    ok, reason = bc.check_inputable(BehaviorControl())
    assert ok and reason == "元素可输入"


def test_inputable_无Pattern拒绝():
    ok, reason = bc.check_inputable(BehaviorControl(value_pattern=False))
    assert not ok and "不支持输入" in reason


def test_hoverable_禁用仍可悬停():
    ok, reason = bc.check_hoverable(BehaviorControl(enabled=False))
    assert ok and reason == "元素可悬停"


def test_布尔属性method形态兼容():
    ok, _ = bc.check_clickable(BehaviorControl(bool_as_method=True))
    assert ok
    ok2, _ = bc.check_clickable(BehaviorControl(bool_as_method=True, enabled=False))
    assert not ok2


def test_run_behavior_check_未知模式按位置放行():
    ok, reason = bc.run_behavior_check(BehaviorControl(enabled=False), bc.VALID_POSITION)
    assert ok and reason == "位置校验"


def test_run_behavior_check_异常按未通过处理():
    class Broken:
        pass

    ok, reason = bc.run_behavior_check(Broken(), "not-a-mode")
    assert ok  # 未知模式放行
    ok2, reason2 = bc.run_behavior_check(None, bc.VALID_CLICK)
    assert not ok2 and "无法读取元素区域" in reason2


# ---------------- ws VALIDATE 集成 ----------------


class _EleWithControl:
    def __init__(self, control):
        self._control = control

    def rect(self):
        return Rect(0, 0, 5, 5)

    def control(self):
        return self._control


def _patch_lm(monkeypatch, ele):
    class _FakeLM:
        def locator(self, data, **kwargs):
            return ele

    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))
    monkeypatch.setattr("astronverse.picker.server.ws_server.time", mock.MagicMock())


def test_ws_validate_click通过(fake_ui, monkeypatch):
    _patch_lm(monkeypatch, _EleWithControl(BehaviorControl()))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VALIDATE, ext_data={"validate_mode": bc.VALID_CLICK})
    result = _run(handler._handle_pick_validate(req))
    assert result == {"success": True, "data": "校验成功(元素可点击)"}


def test_ws_validate_click禁用失败(fake_ui, monkeypatch):
    _patch_lm(monkeypatch, _EleWithControl(BehaviorControl(enabled=False)))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VALIDATE, ext_data={"validate_mode": bc.VALID_CLICK})
    result = _run(handler._handle_pick_validate(req))
    assert result["success"] is False
    assert "禁用" in result["error"]


def test_ws_validate_input无Pattern失败(fake_ui, monkeypatch):
    _patch_lm(monkeypatch, _EleWithControl(BehaviorControl(value_pattern=False)))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VALIDATE, ext_data={"validate_mode": bc.VALID_INPUT})
    result = _run(handler._handle_pick_validate(req))
    assert result["success"] is False
    assert "不支持输入" in result["error"]


def test_ws_validate_坐标定位跳过行为校验(fake_ui, monkeypatch):
    _patch_lm(monkeypatch, _EleWithControl(None))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VALIDATE, ext_data={"validate_mode": bc.VALID_HOVER})
    result = _run(handler._handle_pick_validate(req))
    assert result["success"] is True
    assert "行为校验已跳过" in result["data"]


def test_ws_validate_缺省仍为位置校验(fake_ui, monkeypatch):
    """未传 validate_mode 时行为与原有完全一致(向后兼容)"""
    _patch_lm(monkeypatch, _EleWithControl(BehaviorControl()))
    handler = PickerRequestHandler(_FakeSvc())
    result = _run(handler._handle_pick_validate(PickerRequire(pick_sign=PickerSign.VALIDATE)))
    assert result == {"success": True, "data": "校验成功"}
