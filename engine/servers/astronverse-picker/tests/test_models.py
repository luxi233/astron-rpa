"""拾取器基础模型单测: Point/Rect/OperationResult/枚举/常量表 (picker/__init__.py)"""

from astronverse.picker import (
    APP,
    CHROME_LIKE_BROWSER_TYPES,
    MSAA_APPLICATIONS,
    BROWSER_UIA_POINT_CLASS,
    PICKER_TYPE_DICT,
    OperationResult,
    OperationResultStatus,
    PickerDomain,
    PickerSign,
    PickerType,
    Point,
    Rect,
    ZERO_POINT,
)


class TestPoint:
    def test_坐标与零点(self):
        p = Point(3, 5)
        assert (p.x, p.y) == (3, 5)
        assert (ZERO_POINT.x, ZERO_POINT.y) == (0, 0)


class TestRect:
    def test_宽高与面积(self):
        r = Rect(0, 0, 10, 20)
        assert r.width() == 10
        assert r.height() == 20
        assert r.area() == 200

    def test_负面积为0(self):
        assert Rect(10, 10, 0, 0).area() == 0
        assert Rect.calculate_area(10, 10, 5, 5) == 0

    def test_包含点(self):
        r = Rect(0, 0, 100, 100)
        assert r.contains(Point(0, 0)) is True  # 左上闭
        assert r.contains(Point(99, 99)) is True
        assert r.contains(Point(100, 50)) is False  # 右开
        assert r.contains(Point(-1, 0)) is False
        assert Rect.check_point_containment(0, 0, 10, 10, Point(5, 5)) is True

    def test_包含矩形(self):
        outer = Rect(0, 0, 100, 100)
        assert outer.contains_rect(Rect(10, 10, 90, 90)) is True
        assert outer.contains_rect(Rect(-5, 0, 50, 50)) is False

    def test_相等与序列化(self):
        import json

        assert Rect(1, 2, 3, 4) == Rect(1, 2, 3, 4)
        assert Rect(1, 2, 3, 4) != Rect(1, 2, 3, 5)
        assert json.loads(Rect(1, 2, 3, 4).to_json()) == {"left": 1, "top": 2, "right": 3, "bottom": 4}

    def test_面积缓存不被负值污染(self):
        r = Rect(5, 5, 15, 15)
        assert r.area() == 100
        r2 = Rect(15, 15, 5, 5)
        assert r2.area() == 0  # 首次计算为负 → max(0)


class TestOperationResult:
    def test_success(self):
        d = OperationResult.success(data={"a": 1}).to_dict()
        assert d == {"success": True, "data": {"a": 1}}

    def test_success_无data不携带键(self):
        assert OperationResult.success().to_dict() == {"success": True}

    def test_error(self):
        d = OperationResult.error("boom").to_dict()
        assert d == {"success": False, "error": "boom"}

    def test_error_空消息兜底(self):
        assert OperationResult.error(None).to_dict()["error"] == "未知错误"

    def test_cancel(self):
        d = OperationResult.cancel().to_dict()
        assert d == {"success": False, "cancel": True}

    def test_data_none与空串区分(self):
        # data="" 是合法值但 to_dict 中 `is not None` 应保留空串
        d = OperationResult.success(data="").to_dict()
        assert d["data"] == ""


class TestEnums:
    def test_PickerType全集(self):
        assert {p.value for p in PickerType} == {"ELEMENT", "WINDOW", "POINT", "SIMILAR", "BATCH"}
        assert PICKER_TYPE_DICT == {p.value: True for p in PickerType}

    def test_PickerSign含录制与智能组件(self):
        values = {s.value for s in PickerSign}
        assert {"START", "STOP", "VALIDATE", "GAIN", "HIGHLIGHT", "RECORD", "SMART_COMPONENT"} <= values

    def test_PickerDomain多域(self):
        values = {d.value for d in PickerDomain}
        assert {"uia", "web", "msaa", "SAP", "jab"} <= values

    def test_APP_init别名与未知(self):
        assert APP.init("msedge") is APP.Edge
        assert APP.init("chrome") is APP.Chrome
        assert APP.init("not-a-browser") is APP.Unknown


class TestBrowserConstants:
    def test_点类映射覆盖chromium系浏览器(self):
        for browser in CHROME_LIKE_BROWSER_TYPES:
            assert browser in BROWSER_UIA_POINT_CLASS, f"{browser} 缺少 UIA 点位映射"

    def test_MSAA应用存在(self):
        assert APP.Thunder.value in MSAA_APPLICATIONS
