"""捕获模式化(Phase H)单测。

覆盖:
1. 标准模式 UIA+MSAA 并行试探择优(auto_default_strategy / auto_default_strategy_desk)
2. 深度模式 deep 标记传导(uia_strategy -> UIAPicker.get_element -> 遍历深度)
3. pick_mode=DeepUIA 时 _draw_element 写入 deep 标记且不污染外部入参 dict
"""

from types import SimpleNamespace

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件) + comtypes/pywin MSAA 桩
import test_uia_similar_locator as _similar  # noqa: F401
from test_msaa_similar import _install_msaa_stubs  # noqa: E402

_install_msaa_stubs()

# COMError 仅 Windows 版 _ctypes 存在, auto_strategy 模块级导入需补桩
import _ctypes  # noqa: E402

if not hasattr(_ctypes, "COMError"):
    _ctypes.COMError = type("COMError", (Exception,), {})

from astronverse.picker import APP, PickerDomain, PickerType, Point, Rect  # noqa: E402
from astronverse.picker.strategy import msaa_strategy, uia_strategy  # noqa: E402
from astronverse.picker.strategy.auto_strategy import auto_default_strategy  # noqa: E402
from astronverse.picker.strategy.auto_strategy_desk import auto_default_strategy_desk  # noqa: E402


class _FakeEle:
    """面积可控的假元素(择优逻辑只看 rect().area())"""

    def __init__(self, area: int):
        self._area = area

    def rect(self) -> Rect:
        return Rect(0, 0, 1, self._area)

    def tag(self) -> str:
        return "fake"


def _svc():
    return SimpleNamespace(
        app=APP.Unknown,  # 非浏览器, 走桌面标准模式分支
        process_id=1,
        last_point=Point(10, 10),
        start_control=object(),
        data={},
    )


def _patch_strategies(monkeypatch, msaa_res, uia_res):
    """桩掉两域试探函数。传入 Exception 实例则令对应域抛异常"""

    def _mk(res):
        def _fn(strategy_svc):
            if isinstance(res, Exception):
                raise res
            return res

        return _fn

    monkeypatch.setattr(msaa_strategy, "msaa_default_strategy", _mk(msaa_res))
    monkeypatch.setattr(uia_strategy, "uia_default_strategy", _mk(uia_res))


class TestStandardModeParallelProbe:
    """标准模式: UIA + MSAA 并行试探, 双成功取面积小者"""

    def test_双成功取面积小者_msaa更小(self, monkeypatch):
        msaa_ele, uia_ele = _FakeEle(50), _FakeEle(100)
        _patch_strategies(monkeypatch, msaa_ele, uia_ele)
        assert auto_default_strategy(None, None, _svc()) is msaa_ele

    def test_双成功取面积小者_uia更小(self, monkeypatch):
        msaa_ele, uia_ele = _FakeEle(200), _FakeEle(100)
        _patch_strategies(monkeypatch, msaa_ele, uia_ele)
        assert auto_default_strategy(None, None, _svc()) is uia_ele

    def test_msaa异常仅用uia(self, monkeypatch):
        uia_ele = _FakeEle(100)
        _patch_strategies(monkeypatch, Exception("COM 挂死"), uia_ele)
        assert auto_default_strategy(None, None, _svc()) is uia_ele

    def test_uia异常仅用msaa(self, monkeypatch):
        msaa_ele = _FakeEle(100)
        _patch_strategies(monkeypatch, msaa_ele, Exception("UIA 遍历失败"))
        assert auto_default_strategy(None, None, _svc()) is msaa_ele

    def test_双失败返回None(self, monkeypatch):
        _patch_strategies(monkeypatch, None, None)
        assert auto_default_strategy(None, None, _svc()) is None

    def test_desk策略与AUTO行为一致(self, monkeypatch):
        # 双成功取小
        msaa_ele, uia_ele = _FakeEle(50), _FakeEle(100)
        _patch_strategies(monkeypatch, msaa_ele, uia_ele)
        assert auto_default_strategy_desk(None, None, _svc()) is msaa_ele
        # 双失败返回 None(修复原 desk 无 MSAA 兜底的不一致)
        _patch_strategies(monkeypatch, None, None)
        assert auto_default_strategy_desk(None, None, _svc()) is None
        # MSAA 异常不阻断 UIA
        _patch_strategies(monkeypatch, Exception("boom"), uia_ele)
        assert auto_default_strategy_desk(None, None, _svc()) is uia_ele


class TestDeepMode:
    """深度模式: deep 标记 -> max_depth 传导 -> UIA 更深遍历"""

    def test_deep标记使max_depth翻倍(self, monkeypatch):
        captured = {}

        def _fake_get_element(root, point, **kwargs):
            captured.update(kwargs)
            return _FakeEle(1)

        monkeypatch.setattr(uia_strategy.uia_picker, "get_element", _fake_get_element)
        monkeypatch.setattr(uia_strategy, "UIAElement", lambda control: _FakeEle(1))

        from astronverse.picker.engines.uia_picker import UIAPicker

        svc = _svc()
        svc.data = {"deep": True}
        uia_strategy.uia_default_strategy(svc)
        assert captured["max_depth"] == UIAPicker.MAX_SEARCH_DEPTH * 2

    def test_标准模式不传max_depth(self, monkeypatch):
        captured = {}

        def _fake_get_element(root, point, **kwargs):
            captured.update(kwargs)
            return _FakeEle(1)

        monkeypatch.setattr(uia_strategy.uia_picker, "get_element", _fake_get_element)
        monkeypatch.setattr(uia_strategy, "UIAElement", lambda control: _FakeEle(1))

        svc = _svc()
        svc.data = {}
        uia_strategy.uia_default_strategy(svc)
        assert "max_depth" not in captured

    def test_get_element透传max_depth至遍历(self, monkeypatch):
        from astronverse.picker.engines.uia_picker import UIAPicker, uia_picker

        captured = {}

        def _fake_search(res_list, control, point, ignore_parent_zero=False, deep=1, max_depth=None):
            captured["max_depth"] = max_depth

        monkeypatch.setattr(UIAPicker, "_search_elements_recursively", classmethod(lambda cls, *a, **k: _fake_search(*a, **k)))
        root = SimpleNamespace(control=object(), rect=lambda: Rect(0, 0, 10, 10))  # 无句柄属性 -> 缓存键为 None, 跳过缓存
        uia_picker.get_element(root=root, point=Point(0, 0), used_cache=True, root_need_init=False, max_depth=80)
        assert captured["max_depth"] == 80

    def test_get_element缺省max_depth为None(self, monkeypatch):
        from astronverse.picker.engines.uia_picker import UIAPicker, uia_picker

        captured = {}

        def _fake_search(res_list, control, point, ignore_parent_zero=False, deep=1, max_depth=None):
            captured["max_depth"] = max_depth

        monkeypatch.setattr(UIAPicker, "_search_elements_recursively", classmethod(lambda cls, *a, **k: _fake_search(*a, **k)))
        root = SimpleNamespace(control=object(), rect=lambda: Rect(0, 0, 10, 10))
        uia_picker.get_element(root=root, point=Point(0, 0), root_need_init=False)
        assert captured["max_depth"] is None


class TestDeepUIADrawElement:
    """pick_mode=DeepUIA: _draw_element 写入 deep 标记且不污染外部入参"""

    def test_deep标记写入且不污染原dict(self, monkeypatch):
        from astronverse.picker.core import picker_core_win as pcw

        monkeypatch.setattr(pcw.UIAOperate, "get_cursor_pos", classmethod(lambda cls: (10, 10)))
        monkeypatch.setattr(pcw.UIAOperate, "get_windows_by_point", classmethod(lambda cls, point: object()))
        monkeypatch.setattr(pcw.UIAOperate, "get_process_id", classmethod(lambda cls, control: 1))
        monkeypatch.setattr(pcw, "_is_self_elevated", lambda: True)

        gen_svc_kwargs = {}

        class _FakeStrategy:
            def gen_svc(self, **kwargs):
                gen_svc_kwargs.update(kwargs)
                # 返回的策略上下文携带 data, 供 run 验证 deep 标记
                return SimpleNamespace(app=APP.Unknown, data=kwargs.get("data"))

            def run(self, strategy_svc):
                # 验证 deep 标记已随 data 传入策略上下文
                assert strategy_svc.data.get("deep") is True
                return _FakeEle(100)

        svc = SimpleNamespace(strategy=_FakeStrategy())
        highlight = SimpleNamespace(draw_wnd=lambda *a, **k: None)

        core = pcw.PickerCore()
        data = {"pick_mode": "DeepUIA", "pick_type": PickerType.ELEMENT}
        res = core._draw_element(svc, highlight, data)

        assert res.success
        # 强制 UIA 域(跳过策略试探)
        assert gen_svc_kwargs["domain"] == PickerDomain.UIA
        # 传给策略的 data 携带 deep 标记
        assert gen_svc_kwargs["data"]["deep"] is True
        # 外部原始入参 dict 不被污染(浅拷贝隔离)
        assert "deep" not in data

    def test_标准模式不写deep标记(self, monkeypatch):
        from astronverse.picker.core import picker_core_win as pcw

        monkeypatch.setattr(pcw.UIAOperate, "get_cursor_pos", classmethod(lambda cls: (10, 10)))
        monkeypatch.setattr(pcw.UIAOperate, "get_windows_by_point", classmethod(lambda cls, point: object()))
        monkeypatch.setattr(pcw.UIAOperate, "get_process_id", classmethod(lambda cls, control: 1))
        monkeypatch.setattr(pcw, "_is_self_elevated", lambda: True)

        gen_svc_kwargs = {}

        class _FakeStrategy:
            def gen_svc(self, **kwargs):
                gen_svc_kwargs.update(kwargs)
                return SimpleNamespace(app=APP.Unknown, data=kwargs.get("data"))

            def run(self, strategy_svc):
                return _FakeEle(100)

        svc = SimpleNamespace(strategy=_FakeStrategy())
        highlight = SimpleNamespace(draw_wnd=lambda *a, **k: None)

        core = pcw.PickerCore()
        data = {"pick_type": PickerType.ELEMENT}
        res = core._draw_element(svc, highlight, data)

        assert res.success
        assert gen_svc_kwargs["domain"] == PickerDomain.AUTO  # 缺省自动模式
        assert not gen_svc_kwargs["data"].get("deep")
