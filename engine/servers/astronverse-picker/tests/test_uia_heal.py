"""E2 selector 自愈回归测试。

覆盖:
1. 动态 Name 变化导致精确定位失败时, 自愈放宽 name/value 后命中
2. 结构不变但 cls 变化时, 逐级放宽后命中
3. 元素彻底不存在时自愈失败并返回完整放宽记录
4. 自愈不污染原始元素数据(deepcopy)
5. LocatorManager 集成: 常规定位失败后自动走自愈链路
"""

from copy import deepcopy

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from test_uia_similar_locator import FakeControl  # noqa: E402
from astronverse.locator.core import uia_locator as uia_mod  # noqa: E402


def _node(tag, cls=None, name=None, index=0, disable_keys=None):
    node = {"tag_name": tag, "checked": True, "disable_keys": disable_keys or [], "index": index}
    if cls is not None:
        node["cls"] = cls
    if name is not None:
        node["name"] = name
    return node


def _ele(button_name, win_name="Doc1"):
    return {
        "app": "app",
        "type": "uia",
        "picker_type": "",
        "path": [
            _node("WindowControl", cls="AppWin", name=win_name),
            _node("ButtonControl", cls="BtnCtl", name=button_name),
        ],
    }


def _build_win(button_name):
    button = FakeControl("ButtonControl", cls="BtnCtl", name=button_name)
    return FakeControl("WindowControl", cls="AppWin", name="Doc1", children=[button], handle=1001), button


@pytest.fixture()
def patch_env(monkeypatch):
    def _patch(win):
        monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: [1001])
        monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
        monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: win)
        monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
        monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)

    return _patch


# ---------------- 核心自愈链路 ----------------


def test_heal_name变化放宽后命中(patch_env):
    win, button = _build_win("新名称")
    patch_env(win)
    ele = _ele("旧名称")
    res = uia_mod.UIAFactory.heal(ele, picker_type="")
    assert res["healed"] is True
    assert res["locator"].control() is button
    # 逐层修复: 只放宽定位失败的第2层 name/value
    assert res["relaxations"] == ["第2层放宽name/value"]
    assert "放宽条件" in res["repair_hint"]


def test_heal_cls变化二级放宽后命中(patch_env):
    win = FakeControl("WindowControl", cls="AppWin", name="Doc1", handle=1001)
    button = FakeControl("ButtonControl", cls="RenamedCtl", name="同名")
    win._children = [button]
    button._parent = win
    patch_env(win)
    ele = _ele("同名")
    res = uia_mod.UIAFactory.heal(ele, picker_type="")
    assert res["healed"] is True
    assert res["locator"].control() is button
    # name 相同未放宽, cls 不同 → 第一级(name/value)不够, 第二级放宽 cls 命中
    assert len(res["relaxations"]) == 2


def test_heal彻底失败返回全部放宽记录(patch_env):
    win = FakeControl("WindowControl", cls="AppWin", name="Doc1", children=[], handle=1001)
    patch_env(win)
    res = uia_mod.UIAFactory.heal(_ele("任意"), picker_type="")
    assert res["healed"] is False
    assert res["locator"] is None
    # 逐层修复(失败层四步) + 全局放宽(HEAL_STAGES) 全部尝试过
    assert len(res["relaxations"]) == len(uia_mod.LAYER_RELAX_STEPS) + len(uia_mod.HEAL_STAGES)
    assert res["repair_hint"] == ""


def test_heal不污染原始元素数据(patch_env):
    win, _ = _build_win("新名称")
    patch_env(win)
    ele = _ele("旧名称")
    snapshot = deepcopy(ele)
    uia_mod.UIAFactory.heal(ele, picker_type="")
    assert ele == snapshot


def test_heal空路径不崩溃():
    res = uia_mod.UIAFactory.heal({"type": "uia"}, picker_type="")
    assert res["healed"] is False


# ---------------- LocatorManager 集成 ----------------


def test_manager定位失败自动自愈(patch_env, monkeypatch):
    win, button = _build_win("新名称")
    patch_env(win)
    from astronverse.locator.locator import LocatorManager

    res = LocatorManager().locator(_ele("旧名称"))
    assert res is not None
    assert res.control() is button


def test_manager可关闭自愈(patch_env):
    win = FakeControl("WindowControl", cls="AppWin", name="Doc1", children=[], handle=1001)
    patch_env(win)
    from astronverse.locator.locator import LocatorManager

    with pytest.raises(Exception):
        LocatorManager().locator(_ele("不存在"), self_heal=False)
