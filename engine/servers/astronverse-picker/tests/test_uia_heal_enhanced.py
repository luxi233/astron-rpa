"""E2 selector 自愈增强回归测试(逐层修复/跳层/多候选择优)。

覆盖:
1. 中间层被插入(结构变化)时, 失败层逐步放宽后"跳层(后代搜索)"命中 —— 对齐用户手工删层
2. 放宽后出现多个候选时, 按属性重合度择优(name 仍匹配的优先)
3. 属性重合度打分单测(含已禁用键)
4. 后代遍历深度受控
"""

import test_uia_similar_locator as _similar  # noqa: F401
from test_uia_heal import _node, patch_env  # noqa: E402
from test_uia_similar_locator import FakeControl  # noqa: E402
from astronverse.locator.core import uia_locator as uia_mod  # noqa: E402
from astronverse.locator.core.uia_locator import UIAEle, UIANode  # noqa: E402,F811


def _ele_with_pane(button_name):
    return {
        "app": "app",
        "type": "uia",
        "picker_type": "",
        "path": [
            _node("WindowControl", cls="AppWin", name="Doc1"),
            _node("PaneControl", cls="PaneCtl", name="主面板"),
            _node("ButtonControl", cls="BtnCtl", name=button_name),
        ],
    }


def test_heal_中间层被插入跳层修复(patch_env, monkeypatch):
    """拾取后应用改版在 Pane 与 Button 之间插入了 Group 层(结构变化)"""
    button = FakeControl("ButtonControl", cls="BtnCtl", name="确定")
    group = FakeControl("GroupControl", cls="GroupCtl", name="分组")
    pane = FakeControl("PaneControl", cls="PaneCtl", name="主面板", children=[group])
    group._children = [button]
    button._parent = group
    win = FakeControl("WindowControl", cls="AppWin", name="Doc1", children=[pane], handle=1001)
    patch_env(win)

    res = uia_mod.UIAFactory.heal(_ele_with_pane("确定"), picker_type="")
    assert res["healed"] is True
    assert res["locator"].control() is button
    # 第3层(Button)属性全放宽无解后, 跳层在 Pane 后代中命中
    assert res["relaxations"][-1] == "第3层跳层(后代搜索)"
    # 跳层前的属性放宽不应波及窗口层与 Pane 层(手术式)
    assert all(r.startswith("第3层") for r in res["relaxations"])


def test_heal_多候选按属性重合度择优(patch_env):
    """放宽 cls 后两个按钮均命中, name 仍匹配的应被选中"""
    btn_match_name = FakeControl("ButtonControl", cls="BtnA", name="目标")
    btn_other = FakeControl("ButtonControl", cls="BtnB", name="其他")
    win = FakeControl(
        "WindowControl", cls="AppWin", name="Doc1", children=[btn_match_name, btn_other], handle=1001
    )
    patch_env(win)

    ele = {
        "app": "app",
        "type": "uia",
        "picker_type": "",
        "path": [
            _node("WindowControl", cls="AppWin", name="Doc1"),
            _node("ButtonControl", cls="BtnOld", name="目标"),
        ],
    }
    res = uia_mod.UIAFactory.heal(ele, picker_type="")
    assert res["healed"] is True
    # name="目标" 的候选重合度更高, 优先命中(而非按遍历顺序取"其他")
    assert res["locator"].control() is btn_match_name
    assert res["relaxations"] == ["第2层放宽name/value", "第2层放宽cls"]


def test_属性重合度打分含已禁用键():
    overlap_score = getattr(uia_mod.UIAFactory, "__attr_overlap_score__")
    control = FakeControl("ButtonControl", cls="Btn", name="确定")
    uia_ele = UIAEle(control=control, index=0)
    node = UIANode(tag_name="ButtonControl", checked=True, disable_keys=["name"], cls="Btn", name="确定")
    # name 虽被禁用, 实际仍匹配 → 计入重合度
    score = overlap_score(uia_ele, node)
    assert score == 3  # tag + cls + name

    node_diff = UIANode(tag_name="ButtonControl", checked=True, disable_keys=["name"], cls="Btn", name="取消")
    score_diff = overlap_score(uia_ele, node_diff)
    assert score_diff == 2  # tag + cls


def test_后代遍历深度受控():
    """深层链条下后代遍历不超过 DESCENDANT_SEARCH_MAX_DEPTH 层且不含自身"""
    descendant_walk = getattr(uia_mod.UIAFactory, "__get_descendant_walk_controls__")
    deep = FakeControl("ButtonControl", cls="L5", name="deep")
    l4 = FakeControl("PaneControl", cls="L4", children=[deep])
    l3 = FakeControl("PaneControl", cls="L3", children=[l4])
    l2 = FakeControl("PaneControl", cls="L2", children=[l3])
    root = FakeControl("PaneControl", cls="L1", children=[l2])

    names = [e.cls for e in descendant_walk(root)]
    assert "L1" not in names  # 不含自身
    assert "L5" in names
    assert len(names) == 4

    # 深度上限截断
    names_shallow = [e.cls for e in descendant_walk(root, max_depth=2)]
    assert names_shallow == ["L2", "L3"]
