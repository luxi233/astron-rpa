"""MSAA 相似元素落实回归测试。

MSAA 相似此前为占位实现(get_similar_path 直接抛"暂不支持"), 本次落实:
1. MSAAPicker.get_similar_path: 两条路径泛化为共同祖先+区分层(与 UIA 宽松语义对齐)
2. MSAAValidator 相似模式: 区分层枚举全部匹配分支, disable_keys 放宽属性过滤
3. MSAAValidator.validate 相似模式返回定位器列表(与 UIA 一致供 similar_count 统计)
"""

import sys
import types
from types import SimpleNamespace

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401


def _install_msaa_stubs() -> None:
    """comtypes/pywin 依赖桩(非Windows平台无 MSAA COM 环境)"""
    if "comtypes" not in sys.modules:
        comtypes = types.ModuleType("comtypes")
        automation = types.ModuleType("comtypes.automation")
        automation.VARIANT = type("VARIANT", (), {})
        automation.BSTR = type("BSTR", (), {})
        automation.VT_I4 = 3
        automation.VT_BSTR = 8
        automation.VT_DISPATCH = 9
        client = types.ModuleType("comtypes.client")
        client.GetModule = lambda *a, **k: None
        gen = types.ModuleType("comtypes.gen")
        accessibility = types.ModuleType("comtypes.gen.Accessibility")
        accessibility.IAccessible = type("IAccessible", (), {})
        gen.Accessibility = accessibility
        comtypes.automation = automation
        comtypes.client = client
        comtypes.gen = gen
        sys.modules["comtypes"] = comtypes
        sys.modules["comtypes.automation"] = automation
        sys.modules["comtypes.client"] = client
        sys.modules["comtypes.gen"] = gen
        sys.modules["comtypes.gen.Accessibility"] = accessibility

    if "pywin" not in sys.modules:
        pywin = types.ModuleType("pywin")
        mfc = types.ModuleType("pywin.mfc")
        obj = types.ModuleType("pywin.mfc.object")
        obj.Object = type("Object", (), {})
        mfc.object = obj
        pywin.mfc = mfc
        sys.modules["pywin"] = pywin
        sys.modules["pywin.mfc"] = mfc
        sys.modules["pywin.mfc.object"] = obj


_install_msaa_stubs()

from astronverse.locator import PickerType, Rect  # noqa: E402
from astronverse.locator.core import msaa_locator as ml  # noqa: E402
from astronverse.picker.engines.msaa_picker import MSAAPicker  # noqa: E402


class FakeNode:
    """MSAA 元素鸭子桩: 仅实现路径查找用到的 get_* 接口"""

    def __init__(self, tag, name="", value="", index=0, children=None):
        self._tag = tag
        self._name = name
        self._value = value
        self._index = index
        self.children = children or []

    def get_type(self):
        return self._tag

    def get_name(self):
        return self._name

    def get_value(self):
        return self._value

    def get_index(self):
        return self._index

    def get_children(self):
        return self.children

    def get_rect(self):
        return Rect(0, 0, 10, 10)


def _build_list_tree():
    """Client > List > ListItem x3 + PushButton"""
    items = [FakeNode("ListItem", name=n, index=i) for i, n in enumerate(["邮件A", "邮件B", "邮件C"])]
    items.append(FakeNode("PushButton", name="删除", index=3))
    lst = FakeNode("List", name="邮件列表", children=items)
    return FakeNode("Client", children=[lst])


# ---------------- 路径查找: 相似枚举与 disable_keys ----------------


class TestMsaaPathFind:
    def test_常规模式单点导航取首个匹配(self):
        root = _build_list_tree()
        path = [
            {"tag_name": "List", "name": "邮件列表", "index": 0},
            {"tag_name": "ListItem", "name": "邮件B", "index": 1},
        ]
        res = ml.MSAAValidator.find_element_by_msaa_path(path, root)
        assert isinstance(res, list) and len(res) == 1
        assert res[0].get_name() == "邮件B"

    def test_相似模式区分层枚举全部候选(self):
        root = _build_list_tree()
        path = [
            {"tag_name": "List", "name": "邮件列表", "similar_parent": True},
            {"tag_name": "ListItem", "disable_keys": ["name", "value", "index"]},
        ]
        res = ml.MSAAValidator.find_element_by_msaa_path(path, root, collect_similar=True)
        assert [n.get_name() for n in res] == ["邮件A", "邮件B", "邮件C"]

    def test_相似模式共同祖先层仍单点导航(self):
        # 全部为 similar_parent 层时不触发枚举(差异在 UIA 窗口段的跨实例场景)
        root = _build_list_tree()
        path = [{"tag_name": "List", "name": "邮件列表", "similar_parent": True}]
        res = ml.MSAAValidator.find_element_by_msaa_path(path, root, collect_similar=True)
        assert len(res) == 1 and res[0].get_name() == "邮件列表"

    def test_disable_keys放宽name过滤(self):
        root = _build_list_tree()
        # name 填错但被 disable → 仍能命中
        matches = ml.MSAAValidator._find_matches_in_parent(
            root, {"tag_name": "List", "name": "错误的名字", "disable_keys": ["name"]}
        )
        assert len(matches) == 1 and matches[0].get_name() == "邮件列表"
        # 未 disable 时同名不匹配
        matches = ml.MSAAValidator._find_matches_in_parent(root, {"tag_name": "List", "name": "错误的名字"})
        assert matches == []


class TestMsaaValidateSimilar:
    def test_validate相似模式返回定位器列表(self, monkeypatch):
        root = _build_list_tree()
        monkeypatch.setattr(ml.MSAAValidator, "find_element_by_uia_path", staticmethod(lambda ele, pt: 1234))
        monkeypatch.setattr(ml.MSAAValidator, "_get_msaa_ele_from_hwnd", staticmethod(lambda hwnd, **k: root))
        # MSAAElement 包装 FakeNode, 子级获取委托给桩节点
        monkeypatch.setattr(ml.MSAAElement, "get_children", lambda self: self.IAccessible.get_children())
        ele = {
            "path": [
                {"tag_name": "WindowControl", "cls": "ThunderRT6FormDC", "name": "邮件1"},
                {"tag_name": "List", "name": "邮件列表", "similar_parent": True},
                {"tag_name": "ListItem", "disable_keys": ["name", "value", "index"]},
            ]
        }
        res = ml.MSAAValidator.validate(ele, PickerType.SIMILAR.value)
        assert isinstance(res, list) and len(res) == 3
        assert all(isinstance(x, ml.MSAALocator) for x in res)

    def test_validate常规模式仍返回单一定位器(self, monkeypatch):
        root = _build_list_tree()
        monkeypatch.setattr(ml.MSAAValidator, "find_element_by_uia_path", staticmethod(lambda ele, pt: 1234))
        monkeypatch.setattr(ml.MSAAValidator, "_get_msaa_ele_from_hwnd", staticmethod(lambda hwnd, **k: root))
        monkeypatch.setattr(ml.MSAAElement, "get_children", lambda self: self.IAccessible.get_children())
        ele = {
            "path": [
                {"tag_name": "WindowControl", "cls": "ThunderRT6FormDC", "name": "邮件1"},
                {"tag_name": "List", "name": "邮件列表"},
                {"tag_name": "ListItem", "name": "邮件B", "index": 1},
            ]
        }
        res = ml.MSAAValidator.validate(ele, PickerType.ELEMENT.value)
        assert isinstance(res, ml.MSAALocator)
        assert res.control().get_name() == "邮件B"


# ---------------- 路径泛化: MSAAPicker.get_similar_path ----------------


def _svc(old_ele):
    return SimpleNamespace(data={"data": old_ele, "pick_type": PickerType.SIMILAR})


def _ele(path, app="Thunder", ele_type="msaa"):
    return {"app": app, "type": ele_type, "version": "1", "path": path}


def _win(name, cls="ThunderRT6FormDC"):
    return {"tag_name": "WindowControl", "cls": cls, "name": name, "index": 0, "checked": True}


def _layer(tag, name="", value="", index=0):
    return {"tag_name": tag, "name": name, "value": value, "index": index, "checked": True}


class TestMsaaGetSimilarPath:
    def test_相似成立并标记共同祖先与区分层(self):
        old_path = [
            _win("邮件1 - Thunder"),
            _layer("Client"),
            _layer("List", name="邮件列表"),
            _layer("ListItem", name="邮件A", index=0),
        ]
        new_path = [
            _win("邮件2 - Thunder"),
            _layer("Client"),
            _layer("List", name="邮件列表"),
            _layer("ListItem", name="邮件B", index=1),
        ]
        res = MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path))
        assert res is not None
        # 窗口标题不同 → 根层放宽 name, 仍为共同祖先
        assert res[0]["disable_keys"] == ["name"]
        assert res[0]["similar_parent"] is True
        assert res[1]["similar_parent"] is True
        assert res[2]["similar_parent"] is True
        # 首个区分层仅按角色区分(MSAA 无 cls)
        assert res[3]["disable_keys"] == ["name", "value", "index"]
        assert "similar_parent" not in res[3]

    def test_窗口标题相同则根层不放宽(self):
        old_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="A")]
        new_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="B")]
        res = MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path))
        assert res is not None
        assert "disable_keys" not in res[0]
        assert res[2]["disable_keys"] == ["name", "value", "index"]

    def test_应用或类型不一致判不相似(self):
        path = [_win("邮件1"), _layer("ListItem", name="A")]
        other = [_win("邮件2"), _layer("ListItem", name="B")]
        assert MSAAPicker.get_similar_path(_svc(_ele(path, app="AppA")), _ele(other, app="AppB")) is None
        assert MSAAPicker.get_similar_path(_svc(_ele(path)), _ele(other, ele_type="uia")) is None

    def test_根层角色不同判不相似(self):
        old_path = [_win("邮件1", cls="ThunderRT6FormDC"), _layer("ListItem", name="A")]
        new_path = [_win("邮件2", cls="Notepad"), _layer("ListItem", name="B")]
        assert MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path)) is None

    def test_完全同路径判不相似(self):
        old_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="A", index=0)]
        new_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="A", index=0)]
        assert MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path)) is None

    def test_祖先关系判不相似(self):
        # 新路径是旧路径的真前缀且无分叉
        old_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="A"), _layer("Text", name="正文")]
        new_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="A")]
        assert MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path)) is None

    def test_深度不同时尾部层全部为区分层(self):
        old_path = [
            _win("邮件1"),
            _layer("List"),
            _layer("ListItem", name="A"),
            _layer("Text", name="正文A"),
        ]
        new_path = [_win("邮件1"), _layer("List"), _layer("ListItem", name="B")]
        res = MSAAPicker.get_similar_path(_svc(_ele(old_path)), _ele(new_path))
        assert res is not None
        # ListItem 为首个区分层, 尾部 Text 层为后续区分层(放宽 name/value)
        assert res[2]["disable_keys"] == ["name", "value", "index"]
        assert res[3]["disable_keys"] == ["name", "value"]
