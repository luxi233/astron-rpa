"""桌面拾取属性匹配增强回归测试。

覆盖计划 C1/C2/C5:
1. C1: AutomationId 采集与优先匹配(路径未采集时不作为约束, 兼容旧拾取数据)
2. C2: match_type 模糊匹配(exact/contains/regex, 非法正则退化精确匹配)
3. C5: 定位链路不再依赖 top_window(由 test_uia_similar_locator 回归, 此处仅防再引入)
"""

from types import SimpleNamespace

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from astronverse.locator.core import uia_locator as uia_mod  # noqa: E402
from astronverse.picker.engines.uia_picker import UIAElement  # noqa: E402

compare = getattr(uia_mod.UIAFactory, "__compare_node_and_uia_ele__")


class MatchControl:
    """最小 UIA Control 桩: 仅覆盖匹配所需属性"""

    def __init__(self, tag="ButtonControl", cls="", name="", automation_id=None, value=None):
        self.ControlTypeName = tag
        self.ClassName = cls
        self.Name = name
        if automation_id is not None:
            self.AutomationId = automation_id
        self._value = value
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=10, bottom=10)

    def GetValuePattern(self):
        if self._value is None:
            raise NotImplementedError("no value pattern")
        return SimpleNamespace(Value=self._value)


def _node(**kw):
    base = dict(tag_name="ButtonControl", checked=True, disable_keys=[], cls="", name="")
    base.update(kw)
    return uia_mod.UIANode(**base)


# ---------------- C1: AutomationId ----------------


def test_automation_id_exact_match():
    node = _node(automation_id="btnSubmit")
    assert compare(uia_mod.UIAEle(control=MatchControl(automation_id="btnSubmit")), node, uia_mod.ATTR_MATCH_KEYS)
    assert not compare(uia_mod.UIAEle(control=MatchControl(automation_id="btnCancel")), node, uia_mod.ATTR_MATCH_KEYS)


def test_old_path_without_automation_id_not_constrained():
    # 旧版本拾取数据无 automation_id(None), 不应因此拒绝有 AutomationId 的实际控件
    node = _node(automation_id=None)
    assert compare(uia_mod.UIAEle(control=MatchControl(automation_id="x1")), node, uia_mod.ATTR_MATCH_KEYS)


def test_control_without_automation_id_attr():
    # 控件无 AutomationId 属性(读取异常)时视为空, 与空节点值不冲突
    node = _node(automation_id=None)
    assert compare(uia_mod.UIAEle(control=MatchControl()), node, uia_mod.ATTR_MATCH_KEYS)


def test_automation_id_disabled_skipped():
    node = _node(automation_id="a", disable_keys=["automation_id"])
    assert compare(uia_mod.UIAEle(control=MatchControl(automation_id="b")), node, uia_mod.ATTR_MATCH_KEYS)


# ---------------- C2: 模糊匹配 ----------------


def test_contains_match():
    node = _node(name="订单", match_types={"name": "contains"})
    assert compare(uia_mod.UIAEle(control=MatchControl(name="订单列表2026-08-21")), node, uia_mod.ATTR_MATCH_KEYS)
    assert not compare(uia_mod.UIAEle(control=MatchControl(name="任务列表")), node, uia_mod.ATTR_MATCH_KEYS)


def test_regex_match():
    node = _node(name=r"count:\d+", match_types={"name": "regex"})
    assert compare(uia_mod.UIAEle(control=MatchControl(name="count:42")), node, uia_mod.ATTR_MATCH_KEYS)
    assert not compare(uia_mod.UIAEle(control=MatchControl(name="count:x")), node, uia_mod.ATTR_MATCH_KEYS)


def test_invalid_regex_fallback_to_exact():
    node = _node(name="a[b", match_types={"name": "regex"})
    assert compare(uia_mod.UIAEle(control=MatchControl(name="a[b")), node, uia_mod.ATTR_MATCH_KEYS)
    assert not compare(uia_mod.UIAEle(control=MatchControl(name="other")), node, uia_mod.ATTR_MATCH_KEYS)


def test_default_match_type_is_exact():
    node = _node(name="确定")
    assert compare(uia_mod.UIAEle(control=MatchControl(name="确定")), node, uia_mod.ATTR_MATCH_KEYS)
    assert not compare(uia_mod.UIAEle(control=MatchControl(name="确定按钮")), node, uia_mod.ATTR_MATCH_KEYS)


# ---------------- C1: picker 侧采集 ----------------


class ParentControl(MatchControl):
    def __init__(self, children):
        super().__init__(tag="PaneControl")
        self._children = children

    def GetChildren(self):
        return self._children


def test_picker_empty_attrs_include_automation_id():
    el = UIAElement(control=MatchControl())
    empty = el._get_empty_attrs({"tag_name": "ButtonControl", "automation_id": "btn1"})
    assert "automation_id" not in empty
    empty2 = el._get_empty_attrs({"tag_name": "ButtonControl"})
    assert "automation_id" in empty2


def test_picker_siblings_collect_automation_id():
    self_ctrl = MatchControl(tag="ButtonControl", name="self", automation_id="b1")
    sibling = MatchControl(tag="ButtonControl", name="sib", automation_id="b2")
    other_tag = MatchControl(tag="TextControl", name="other", automation_id="t1")
    parent = ParentControl(children=[self_ctrl, sibling, other_tag])
    el = UIAElement(control=self_ctrl)
    siblings = el._get_siblings_by_tag(parent, self_ctrl, "ButtonControl")
    assert len(siblings) == 1
    assert siblings[0]["automation_id"] == "b2"


# ---------------- C5: 防回归 ----------------


def test_locator_module_no_longer_imports_top_window():
    # 定位链路已移除置顶副作用, 模块不应再持有 top_window 引用
    assert not hasattr(uia_mod, "top_window")
