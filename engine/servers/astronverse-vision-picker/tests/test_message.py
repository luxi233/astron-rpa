"""L3: message 协议模型测试(WS 消息入参/响应结构与枚举)。"""

import pytest
from astronverse.vision_picker.core.message import (
    PickerInputData,
    PickerResponse,
    PickerResponseItem,
    PickerSign,
    PickerType,
)
from pydantic import ValidationError


class TestPickerSign:
    def test枚举值稳定(self):
        assert {s.value for s in PickerSign} == {"START", "STOP", "VALIDATE", "DESIGNATE"}

    def test从字符串解析(self):
        assert PickerSign("VALIDATE") is PickerSign.VALIDATE


class TestPickerType:
    def test包含CV拾取类型(self):
        assert PickerType("CV") is PickerType.CV
        assert {t.value for t in PickerType} >= {"ELEMENT", "WINDOW", "POINT", "SIMILAR", "CV"}


class TestPickerInputData:
    def test默认值(self):
        data = PickerInputData()
        assert data.pick_sign is PickerSign.START
        assert data.pick_type is PickerType.ELEMENT
        assert data.data is None
        assert data.ext_data == {}

    def test完整构造(self):
        data = PickerInputData(
            pick_sign=PickerSign.VALIDATE, pick_type=PickerType.CV, data='{"x": 1}', ext_data={"scale": 2}
        )
        assert data.pick_sign is PickerSign.VALIDATE
        assert data.pick_type is PickerType.CV
        assert data.data == '{"x": 1}'
        assert data.ext_data["scale"] == 2

    def test非法pick_sign拒绝(self):
        with pytest.raises(ValidationError):
            PickerInputData(pick_sign="NOT_A_SIGN")

    def test非法pick_type拒绝(self):
        with pytest.raises(ValidationError):
            PickerInputData(pick_type="NOT_A_TYPE")


class TestPickerResponse:
    def test默认key为success(self):
        resp = PickerResponse(err_msg="", data="{}")
        assert resp.key is PickerResponseItem.SUCCESS

    def test错误响应构造(self):
        resp = PickerResponse(err_msg="定位失败", data="", key=PickerResponseItem.ERROR)
        assert resp.key is PickerResponseItem.ERROR
        assert resp.err_msg == "定位失败"

    def test响应key枚举覆盖(self):
        assert {k.value for k in PickerResponseItem} == {"ping", "success", "error", "cancel"}


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
