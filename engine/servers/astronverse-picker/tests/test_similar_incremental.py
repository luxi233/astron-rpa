"""相似元素增量折叠(影刀式多样本泛化)回归测试。

覆盖"泛化结果写回 → 再次作为参照捕获"的多轮循环:
1. disable_keys 并集追加只增不减(旧实现覆盖会把上一轮已放宽的键收窄回去)
2. 第二轮更早分叉时, 首个区分层及之后的过期 similar_parent 全部清除
3. 根层窗口标题放宽并集不重复追加
4. 完全同路径/祖先关系仍判不相似
5. similar_sample_count 逐轮 +1(UIA/MSAA path() 写入)
"""

import sys
import types
from copy import deepcopy
from types import SimpleNamespace

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from test_uia_similar_locator import _node  # noqa: E402


def _install_msaa_stubs() -> None:
    """comtypes/pywin 依赖桩(与 test_msaa_similar 保持一致, 独立可运行)"""
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

import astronverse.locator.locator as locator_mod  # noqa: E402
from astronverse.locator import PickerType, Rect  # noqa: E402
from astronverse.picker import PickerType as PickerPickerType  # noqa: E402  # path() 用的是 picker 侧枚举
from astronverse.picker.engines import msaa_picker as msaa_mod  # noqa: E402
from astronverse.picker.engines import uia_picker as uia_mod  # noqa: E402
from astronverse.picker.engines.msaa_picker import MSAAPicker, MSAAElement  # noqa: E402
from astronverse.picker.engines.uia_picker import UIAPicker, UIAElement  # noqa: E402


def _svc(old_ele):
    return SimpleNamespace(data={"data": old_ele, "pick_type": PickerType.SIMILAR})


def _ele(path, app="app", ele_type="uia", **extra):
    return {"app": app, "type": ele_type, "version": "1", "path": path, **extra}


# ---------------- A: UIA 增量折叠 ----------------


class TestUiaIncrementalFold:
    def _round(self, ref_path, new_path, extra_ref=None):
        old = _ele(ref_path, **(extra_ref or {}))
        return UIAPicker.get_similar_path(_svc(old), _ele(new_path))

    def test_三轮折叠_disable_keys只增不减(self):
        # 第1轮: A∧B → ListItem 成为首个区分层(放宽 cls/name/value/index)
        path_a = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path_b = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        g1 = self._round(path_a, path_b)
        assert g1 is not None
        assert set(g1[2]["disable_keys"]) == {"cls", "name", "value", "index"}

        # 第2轮: G1∧C, C 在 Pane 层提前分叉 → ListItem 成为"后续区分层",
        # 旧实现会覆盖为 ["name","value"] 收窄规则, 增量折叠必须保持并集
        path_c = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M2"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        g2 = self._round(deepcopy(g1), path_c)
        assert g2 is not None
        assert {"cls", "name", "value", "index"} <= set(g2[2]["disable_keys"]), "已放宽的键不得被后续轮次收窄"
        # Pane 为本轮首个区分层, 仅按 tag 区分
        assert set(g2[1]["disable_keys"]) == {"cls", "name", "value", "index"}

    def test_第二轮更早分叉_清除过期similar_parent(self):
        path_a = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListControl", cls="L", name="任务列表"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path_b = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M"),
            _node("ListControl", cls="L", name="任务列表"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        g1 = self._round(path_a, path_b)
        assert g1[1].get("similar_parent") is True
        assert g1[2].get("similar_parent") is True

        # C 在 Pane 层分叉: Pane/List 不再是共同祖先, 残留标记会误导定位锚定
        path_c = [
            _node("WindowControl", cls="W", name="D"),
            _node("PaneControl", cls="P", name="M2"),
            _node("ListControl", cls="L", name="任务列表"),
            _node("ListItemControl", cls="LI", name="C", index=2),
        ]
        g2 = self._round(deepcopy(g1), path_c)
        assert g2[0]["similar_parent"] is True  # 窗口层恒为锚定层
        for i in range(1, len(g2)):
            assert not g2[i].get("similar_parent"), f"第{i}层过期 similar_parent 未清除"

    def test_根层窗口标题放宽并集不重复(self):
        path_a = [
            _node("WindowControl", cls="W", name="Doc1"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path_b = [
            _node("WindowControl", cls="W", name="Doc2"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        g1 = self._round(path_a, path_b)
        assert g1[0]["disable_keys"].count("name") == 1

        path_c = [
            _node("WindowControl", cls="W", name="Doc3"),
            _node("ListItemControl", cls="LI", name="C", index=2),
        ]
        g2 = self._round(deepcopy(g1), path_c)
        assert g2[0]["disable_keys"].count("name") == 1
        assert g2[0]["similar_parent"] is True

    def test_第二轮与参照全同值_仍判不相似(self):
        path_a = [
            _node("WindowControl", cls="W", name="D"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        path_b = [
            _node("WindowControl", cls="W", name="D"),
            _node("ListItemControl", cls="LI", name="B", index=1),
        ]
        g1 = self._round(path_a, path_b)
        # 重新捕获与参照 A 完全相同的元素 → 不构成新样本
        path_same = [
            _node("WindowControl", cls="W", name="D"),
            _node("ListItemControl", cls="LI", name="A", index=0),
        ]
        assert self._round(deepcopy(g1), path_same) is None


# ---------------- B: MSAA 增量折叠 ----------------


def _win(name, cls="ThunderRT6FormDC"):
    return {"tag_name": "WindowControl", "cls": cls, "name": name, "index": 0, "checked": True}


def _layer(tag, name="", value="", index=0):
    return {"tag_name": tag, "name": name, "value": value, "index": index, "checked": True}


class TestMsaaIncrementalFold:
    def _round(self, ref_path, new_path):
        old = _ele(ref_path, app="Thunder", ele_type="msaa")
        return MSAAPicker.get_similar_path(_svc(old), _ele(new_path, app="Thunder", ele_type="msaa"))

    def test_三轮折叠_disable_keys只增不减(self):
        path_a = [_win("邮件1"), _layer("List", name="列表"), _layer("ListItem", name="A", index=0)]
        path_b = [_win("邮件1"), _layer("List", name="列表"), _layer("ListItem", name="B", index=1)]
        g1 = self._round(path_a, path_b)
        assert g1 is not None
        # MSAA 无 cls: 首个区分层放宽 name/value/index
        assert set(g1[2]["disable_keys"]) == {"name", "value", "index"}

        # 第2轮 List 层提前分叉 → ListItem 成为后续区分层, 旧实现覆盖为 ["name","value"]
        path_c = [_win("邮件1"), _layer("List", name="列表2"), _layer("ListItem", name="A", index=0)]
        g2 = self._round(deepcopy(g1), path_c)
        assert g2 is not None
        assert {"name", "value", "index"} <= set(g2[2]["disable_keys"])
        assert set(g2[1]["disable_keys"]) == {"name", "value", "index"}

    def test_第二轮更早分叉_清除过期similar_parent(self):
        path_a = [_win("邮件1"), _layer("Client"), _layer("List", name="列表"), _layer("ListItem", name="A")]
        path_b = [_win("邮件1"), _layer("Client"), _layer("List", name="列表"), _layer("ListItem", name="B")]
        g1 = self._round(path_a, path_b)
        assert g1[2].get("similar_parent") is True

        path_c = [_win("邮件1"), _layer("Client", name="C2"), _layer("List", name="列表"), _layer("ListItem", name="C")]
        g2 = self._round(deepcopy(g1), path_c)
        assert g2[0]["similar_parent"] is True
        for i in range(1, len(g2)):
            assert not g2[i].get("similar_parent")


# ---------------- C: similar_sample_count 样本计数 ----------------


class FakePathControl:
    """最小 UIA Control 桩: 支持 path() 上溯构链"""

    def __init__(self, tag, cls, name, parent=None, index=0):
        self.ControlTypeName = tag
        self.ClassName = cls
        self.Name = name
        self.AutomationId = ""
        self.ProcessId = 1234
        self.NativeWindowHandle = 1001
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=10, bottom=10)
        self._parent = parent
        self._index = index

    def GetParentControl(self):
        return self._parent

    def GetValuePattern(self):
        raise NotImplementedError("no value pattern")


class TestSimilarSampleCount:
    REF_PATH = [
        {"tag_name": "WindowControl", "cls": "W", "name": "D", "index": 0, "checked": True},
        {"tag_name": "PaneControl", "cls": "P", "name": "M", "index": 0, "checked": True, "similar_parent": True},
        {
            "tag_name": "ListItemControl",
            "cls": "LI",
            "name": "A",
            "index": 0,
            "checked": True,
            "disable_keys": ["cls", "name", "value", "index"],
        },
    ]

    def test_uia_path样本计数递增(self, monkeypatch):
        monkeypatch.setattr(uia_mod, "screenshot", lambda r: None)
        monkeypatch.setattr(uia_mod, "get_process_name", lambda pid: "app")
        monkeypatch.setattr(locator_mod, "LocatorManager", lambda: SimpleNamespace(locator=lambda res, timeout=10: [1, 2, 3]))
        monkeypatch.setattr(UIAElement, "index", lambda self: 0)
        monkeypatch.setattr(UIAElement, "_calculate_disable_keys_progressive", lambda self, *a, **k: [])
        monkeypatch.setattr(uia_mod.UIAOperate, "_is_desktop_element", staticmethod(lambda c: False))

        win = FakePathControl("WindowControl", "W", "D")
        pane = FakePathControl("PaneControl", "P", "M", parent=win)
        item = FakePathControl("ListItemControl", "LI", "B", parent=pane, index=1)

        # 参照已累积 2 个样本 → 本轮折叠后应为 3
        old = _ele(deepcopy(self.REF_PATH), img={"self": ""}, similar_sample_count=2)
        strategy_svc = SimpleNamespace(data={"data": old, "pick_type": PickerPickerType.SIMILAR})
        res = UIAElement(control=item).path(strategy_svc=strategy_svc)
        assert res["similar_sample_count"] == 3
        assert res["similar_count"] == 3

        # 旧数据无计数字段 → 缺省按 1, 本轮后为 2
        old2 = _ele(deepcopy(self.REF_PATH), img={"self": ""})
        strategy_svc2 = SimpleNamespace(data={"data": old2, "pick_type": PickerPickerType.SIMILAR})
        res2 = UIAElement(control=item).path(strategy_svc=strategy_svc2)
        assert res2["similar_sample_count"] == 2

    def test_msaa_path样本计数递增(self, monkeypatch):
        monkeypatch.setattr(msaa_mod, "screenshot", lambda r: None)
        monkeypatch.setattr(msaa_mod, "get_process_name", lambda pid: "Thunder")
        monkeypatch.setattr(locator_mod, "LocatorManager", lambda: SimpleNamespace(locator=lambda res, timeout=10: [1]))
        monkeypatch.setattr(msaa_mod.MSAAPickerUtil, "get_rect", staticmethod(lambda ele: Rect(0, 0, 10, 10)))

        msaa_ref = [
            {"tag_name": "WindowControl", "cls": "ThunderRT6FormDC", "name": "邮件1", "index": 0, "checked": True},
            {"tag_name": "List", "name": "列表", "index": 0, "checked": True, "similar_parent": True},
            {"tag_name": "ListItem", "name": "A", "index": 0, "checked": True, "disable_keys": ["name", "value", "index"]},
        ]
        # 本轮捕获的新样本路径(与参照 ListItem 层差异)
        msaa_new = [
            {"tag_name": "WindowControl", "cls": "ThunderRT6FormDC", "name": "邮件1", "index": 0, "checked": True},
            {"tag_name": "List", "name": "列表", "index": 0, "checked": True},
            {"tag_name": "ListItem", "name": "B", "index": 1, "checked": True},
        ]
        monkeypatch.setattr(msaa_mod.MSAAPickerUtil, "get_element_path", staticmethod(lambda ele: deepcopy(msaa_new)))
        old = _ele(deepcopy(msaa_ref), app="Thunder", ele_type="msaa", img={"self": ""}, similar_sample_count=4)
        strategy_svc = SimpleNamespace(data={"data": old, "pick_type": PickerPickerType.SIMILAR})

        class _FakeMsaaNode:
            def get_type(self):
                return "ListItem"

            def get_name(self):
                return "B"

        res = MSAAElement(iaElement=_FakeMsaaNode(), pid=123).path(strategy_svc=strategy_svc)
        assert res["similar_sample_count"] == 5
