"""Web/UIA 相似元素拾取链路回归测试。

覆盖:
1. WEBElement.path SIMILAR: 泛化结果验证 + similar_count/picker_type 透传(0 命中/无结果报错)
2. 智能组件 Web 相似/批量: 占位 raise 已替换为插件委托(similarElement/similarBatch)
3. UIAPicker.get_similar_path: 桌面相似路径泛化(共同祖先/区分层/窗口跨实例/祖先关系)
"""

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from types import SimpleNamespace  # noqa: E402

from astronverse.picker import APP, PickerType, Point  # noqa: E402
from astronverse.picker.engines import web_picker as wp  # noqa: E402
from astronverse.picker.engines.smart_component import web_picker_smart_component as wsc  # noqa: E402
from astronverse.picker.engines.uia_picker import UIAPicker  # noqa: E402


class _Svc:
    """strategy_svc 桩: 仅承载 pick_type 与参照元素数据"""

    def __init__(self, pick_type, ref_path=None, img="IMG"):
        self.route_port = 9082
        self.app = APP.Chrome
        self.data = {
            "pick_type": pick_type,
            "data": {"path": ref_path or {"xpath": "//div"}, "img": {"self": img}},
        }


def _web_info():
    return {"rect": {"x": 0, "y": 0, "right": 10, "bottom": 10}, "tag": "div"}


_PICK_SVC = SimpleNamespace(route_port=9082)  # WEBElement.path 的 svc 仅需 route_port


# ---------------- Web 常规拾取: WEBElement.path SIMILAR ----------------


class TestWEBElementSimilar:
    def test_相似成立透传count与picker_type(self, monkeypatch):
        monkeypatch.setattr(wp, "screenshot", lambda rect: "")
        monkeypatch.setattr(
            wp.WEBPicker, "get_similar_path", staticmethod(lambda route_port, svc: {"xpath": "//a", "similarCount": 5})
        )
        ele = wp.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        res = ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.SIMILAR))
        assert res["path"] == {"xpath": "//a", "similarCount": 5}
        assert res["similar_count"] == 5
        assert res["picker_type"] == PickerType.SIMILAR.value
        assert res["img"]["self"] == "IMG"  # 复用参照元素截图

    def test_泛化命中0个报错(self, monkeypatch):
        monkeypatch.setattr(wp, "screenshot", lambda rect: "")
        monkeypatch.setattr(
            wp.WEBPicker, "get_similar_path", staticmethod(lambda route_port, svc: {"xpath": "//a", "similarCount": 0})
        )
        ele = wp.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        with pytest.raises(Exception, match="找不到相识元素"):
            ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.SIMILAR))

    def test_插件无结果报错(self, monkeypatch):
        monkeypatch.setattr(wp, "screenshot", lambda rect: "")
        monkeypatch.setattr(wp.WEBPicker, "get_similar_path", staticmethod(lambda route_port, svc: None))
        ele = wp.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        with pytest.raises(Exception, match="找不到相识元素"):
            ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.SIMILAR))

    def test_普通拾取不走相似分支(self, monkeypatch):
        monkeypatch.setattr(wp, "screenshot", lambda rect: "SELF")
        ele = wp.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        res = ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.ELEMENT))
        assert "picker_type" not in res
        assert "similar_count" not in res
        assert res["img"]["self"] == "SELF"


# ---------------- 智能组件: 相似/批量委托插件 ----------------


class TestSmartComponentSimilar:
    def test_相似拾取委托similarElement(self, monkeypatch):
        calls = []

        def _send(**kwargs):
            calls.append(kwargs)
            return {"xpath": "//li", "similarCount": 3}

        monkeypatch.setattr(wsc.Browser, "send_browser_extension", staticmethod(_send))
        res = wsc.WEBPicker.get_similar_path(9082, _Svc(PickerType.SIMILAR, ref_path={"xpath": "//li[1]"}))
        assert res["similarCount"] == 3
        assert calls[0]["key"] == "similarElement"
        assert calls[0]["browser_type"] == APP.Chrome.value
        assert calls[0]["data"] == {"xpath": "//li[1]"}

    def test_批量抓取委托similarBatch(self, monkeypatch):
        calls = []

        def _send(**kwargs):
            calls.append(kwargs)
            return {"value": [{"text": "a"}]}

        monkeypatch.setattr(wsc.Browser, "send_browser_extension", staticmethod(_send))
        curr = wsc.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        res = wsc.WEBPicker.get_batch_path(9082, _Svc(PickerType.BATCH), curr)
        assert res == {"value": [{"text": "a"}]}
        assert calls[0]["key"] == "similarBatch"
        assert calls[0]["data"] == _web_info()

    def test_智能组件相似路径验证与透传(self, monkeypatch):
        monkeypatch.setattr(wsc, "screenshot", lambda rect: "")
        monkeypatch.setattr(
            wsc.WEBPicker, "get_similar_path", staticmethod(lambda route_port, svc: {"xpath": "//li", "similarCount": 2})
        )
        ele = wsc.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        res = ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.SIMILAR))
        assert res["similar_count"] == 2
        assert res["picker_type"] == PickerType.SIMILAR.value

    def test_智能组件相似0命中报错(self, monkeypatch):
        monkeypatch.setattr(wsc, "screenshot", lambda rect: "")
        monkeypatch.setattr(
            wsc.WEBPicker, "get_similar_path", staticmethod(lambda route_port, svc: {"xpath": "//li", "similarCount": 0})
        )
        ele = wsc.WEBElement(web_info=_web_info(), left_top_point=Point(0, 0), app=APP.Chrome)
        with pytest.raises(Exception, match="找不到相识元素"):
            ele.path(svc=_PICK_SVC, strategy_svc=_Svc(PickerType.SIMILAR))


# ---------------- 桌面: UIAPicker.get_similar_path 泛化 ----------------


def _uia_svc(old_ele):
    svc = _Svc(PickerType.SIMILAR)
    svc.data["data"] = old_ele
    return svc


def _uia_ele(path, app="notepad"):
    return {"app": app, "type": "uia", "version": "1", "path": path}


def _uia_win(name, cls="Notepad"):
    return {"tag_name": "WindowControl", "cls": cls, "name": name, "index": 0, "checked": True}


def _uia_layer(tag, cls="", name="", index=0):
    return {"tag_name": tag, "cls": cls, "name": name, "value": "", "index": index, "checked": True}


class TestUIAGetSimilarPath:
    def test_相似成立并标记(self):
        old_path = [
            _uia_win("文档1"),
            _uia_layer("ListControl", cls="ListBox"),
            _uia_layer("ListItemControl", name="条目A", index=0),
        ]
        new_path = [
            _uia_win("文档2"),
            _uia_layer("ListControl", cls="ListBox"),
            _uia_layer("ListItemControl", name="条目B", index=1),
        ]
        res = UIAPicker.get_similar_path(_uia_svc(_uia_ele(old_path)), _uia_ele(new_path))
        assert res is not None
        assert res[0]["disable_keys"] == ["name"]  # 窗口标题不同 → 放宽 name 跨实例
        assert res[0]["similar_parent"] is True
        assert res[1]["similar_parent"] is True
        assert res[2]["disable_keys"] == ["cls", "name", "value", "index"]  # 首个区分层仅 tag

    def test_应用或类型不一致判不相似(self):
        path = [_uia_win("文档1"), _uia_layer("ListItemControl", name="A")]
        other = [_uia_win("文档2"), _uia_layer("ListItemControl", name="B")]
        assert UIAPicker.get_similar_path(_uia_svc(_uia_ele(path, app="a")), _uia_ele(other, app="b")) is None
        assert UIAPicker.get_similar_path(_uia_svc(_uia_ele(path)), _uia_ele(other) | {"type": "web"}) is None

    def test_完全同路径与祖先关系判不相似(self):
        base = [_uia_win("文档1"), _uia_layer("ListControl"), _uia_layer("ListItemControl", name="A")]
        # 完全同路径(同一元素)
        same = [_uia_win("文档1"), _uia_layer("ListControl"), _uia_layer("ListItemControl", name="A")]
        assert UIAPicker.get_similar_path(_uia_svc(_uia_ele(base)), _uia_ele(same)) is None
        # 新路径是旧路径真前缀 → 祖先关系
        deeper = base + [_uia_layer("TextControl", name="正文")]
        assert UIAPicker.get_similar_path(_uia_svc(_uia_ele(deeper)), _uia_ele(same)) is None

    def test_深度不同时尾部层为区分层(self):
        old_path = [
            _uia_win("文档1"),
            _uia_layer("ListItemControl", name="A"),
            _uia_layer("TextControl", name="正文A"),
        ]
        new_path = [_uia_win("文档1"), _uia_layer("ListItemControl", name="B")]
        res = UIAPicker.get_similar_path(_uia_svc(_uia_ele(old_path)), _uia_ele(new_path))
        assert res is not None
        assert res[1]["disable_keys"] == ["cls", "name", "value", "index"]
        assert res[2]["disable_keys"] == ["name", "value"]
