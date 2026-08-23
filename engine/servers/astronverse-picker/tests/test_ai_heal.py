"""E4 AI 修复元素回归测试。

覆盖:
1. prompt 输出解析(_extract_path): 合法 UIA/Web path / 非法输出 / JSON 外裹说明文字
2. 网关端口解析链(resolve_gateway_port): 配置注入 → 环境变量 → gateway.json → 默认
3. ai_heal 主函数: LLM 给出修正路径 / 网关不可达 / 输出非法 / 全局开关关闭
4. LocatorManager 集成: 规则自愈与 CV 降级均未命中后 AI 修复成功, 缓存持久化与指标回写
"""

import json

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from astronverse.locator.core import ai_heal as ai_heal_mod
from astronverse.locator.core.ai_heal import (  # noqa: E402
    _build_failure_report,
    _element_context,
    _extract_path,
    ai_heal,
    resolve_gateway_port,
)


def _uia_path(name):
    return [
        {"tag_name": "WindowControl", "cls": "AppWin", "name": "Doc1", "index": 0},
        {"tag_name": "ButtonControl", "cls": "BtnCtl", "name": name, "index": 0},
    ]


def _ele(name, **extra):
    ele = {"app": "app", "type": "uia", "picker_type": "", "path": _uia_path(name)}
    ele.update(extra)
    return ele


def test_element_context_剔除img并截断超长字段():
    ele = {"app": "app", "type": "uia", "path": _uia_path("按钮")}
    ele["img"] = {"self": "base64..."}
    ele["name"] = "x" * 5000


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


# ---------------- 输出解析 ----------------


def test_extract_path_合法UIA数组():
    content = '{"path": [{"tag_name": "WindowControl", "name": "W"}, {"tag_name": "ButtonControl"}]}'
    path = _extract_path(content)
    assert isinstance(path, list) and len(path) == 2


def test_extract_path_合法Web对象():
    content = '{"path": {"xpath": "//button[@id=\\"save\\"]"}}'
    path = _extract_path(content)
    assert isinstance(path, dict) and path["xpath"].startswith("//button")


def test_extract_path_外裹说明文字():
    content = '好的, 修正后的路径如下:\n```json\n{"path": [{"tag_name": "WindowControl"}]}\n```\n请重新验证'
    path = _extract_path(content)
    assert isinstance(path, list) and path[0]["tag_name"] == "WindowControl"


def test_extract_path_非法输出返回None():
    assert _extract_path("") is None
    assert _extract_path(None) is None
    assert _extract_path("放弃修复, 无法判断") is None
    assert _extract_path('{"error": "no path"}') is None
    # 空数组 / 元素层非 dict 均拒绝
    assert _extract_path('{"path": []}') is None
    assert _extract_path('{"path": ["WindowControl"]}') is None
    assert _extract_path('not a json {"path": 1}') is None


def test_build_failure_report_汇总异常与自愈记录():
    text = _build_failure_report(ValueError("找不到控件"), {"relaxations": ["放宽name", "放宽cls"], "cv_ambiguous": 2})
    assert "找不到控件" in text
    assert "放宽name" in text
    assert "2 处相似命中" in text
    assert _build_failure_report(None, None) == "定位失败(无异常详情)"


# ---------------- 网关端口解析链 ----------------


def test_resolve_port_环境变量优先(monkeypatch, tmp_path):
    monkeypatch.delenv("ASTRON_GATEWAY_PORT", raising=False)
    monkeypatch.setattr(ai_heal_mod.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".astronverse").mkdir()
    (tmp_path / ".astronverse" / "gateway.json").write_text(json.dumps({"route_port": 20000}))
    monkeypatch.setenv("ASTRON_GATEWAY_PORT", "18888")
    assert resolve_gateway_port() == "18888"


def test_resolve_port_gateway_json兜底(monkeypatch, tmp_path):
    monkeypatch.delenv("ASTRON_GATEWAY_PORT", raising=False)
    monkeypatch.setattr(ai_heal_mod.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".astronverse").mkdir()
    (tmp_path / ".astronverse" / "gateway.json").write_text(json.dumps({"route_port": 20000}))
    assert resolve_gateway_port() == "20000"


def test_resolve_port_无任何配置时默认(monkeypatch, tmp_path):
    monkeypatch.delenv("ASTRON_GATEWAY_PORT", raising=False)
    monkeypatch.setattr(ai_heal_mod.Path, "home", staticmethod(lambda: tmp_path))
    assert resolve_gateway_port() == "13159"


# ---------------- ai_heal 主函数 ----------------


def test_ai_heal_返回修正元素(monkeypatch):
    fixed_content = json.dumps({"path": _uia_path("新按钮名")}, ensure_ascii=False)
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse({"code": "0000", "data": fixed_content}),
    )
    monkeypatch.setattr(ai_heal_mod, "resolve_gateway_port", lambda: "13159")

    result = ai_heal(_ele("旧按钮名"), "uia", ValueError("找不到控件"))
    assert result is not None
    assert result["element"]["path"][1]["name"] == "新按钮名"
    assert "AI 修复" in result["repair_hint"]


def test_ai_heal_请求携带失败报告(monkeypatch):
    captured = {}

    def _post(url, json=None, timeout=None):
        captured.update(json=json, url=url, timeout=timeout)
        raise ConnectionError("unreachable")

    monkeypatch.setattr(ai_heal_mod.requests, "post", _post)
    ai_heal(_ele("按钮"), "uia", ValueError("找不到控件"))
    assert captured["url"].endswith("/api/rpa-ai-service/v1/chat/prompt")
    assert captured["timeout"] == ai_heal_mod.AI_HEAL_TIMEOUT
    assert captured["json"]["prompt_type"] == "element_heal"
    assert captured["json"]["stream"] is False
    params = captured["json"]["params"]
    assert params["type"] == "uia"
    assert "找不到控件" in params["report"]
    assert "path" in json.loads(params["element"])


def test_ai_heal_网关不可达返回None(monkeypatch):
    def _post(url, json=None, timeout=None):
        raise ConnectionError("refused")

    monkeypatch.setattr(ai_heal_mod.requests, "post", _post)
    assert ai_heal(_ele("按钮"), "uia") is None


def test_ai_heal_输出非法返回None(monkeypatch):
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse({"code": "0000", "data": "无法修复该元素"}),
    )
    assert ai_heal(_ele("按钮"), "uia") is None


def test_ai_heal_业务错误码返回None(monkeypatch):
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse({"code": "5000", "msg": "上游未配置"}),
    )
    assert ai_heal(_ele("按钮"), "uia") is None


def test_ai_heal_全局开关关闭(monkeypatch):
    def _post(url, json=None, timeout=None):
        raise AssertionError("开关关闭时不应发起网关请求")

    monkeypatch.setattr(ai_heal_mod.requests, "post", _post)
    monkeypatch.setenv("ASTRON_AI_HEAL", "0")
    assert ai_heal(_ele("按钮"), "uia") is None


# ---------------- LocatorManager 集成 ----------------


def _disable_rule_heal(monkeypatch):
    """禁用 E2 规则自愈(避免放宽 name 后命中改名按钮而到不了 E4), 模拟自愈无解"""
    from astronverse.locator.core import uia_locator as uia_mod

    monkeypatch.setattr(
        uia_mod.UIAFactory,
        "heal",
        classmethod(
            lambda cls, ele, picker_type="", **kw: {
                "healed": False,
                "relaxations": ["放宽name"],
                "element": None,
                "repair_hint": "",
                "locator": None,
            }
        ),
    )


def test_manager_AI修复命中并写缓存(monkeypatch):
    from test_uia_heal import _build_win, _ele as _heal_ele
    from astronverse.locator.core import heal_store, uia_locator as uia_mod
    from astronverse.locator.locator import LocatorManager

    # 窗口中按钮已改名 → 原始 name 定位失败, 规则自愈无解(mock 禁用), 无 img 跳过 CV 降级
    win, _ = _build_win("改名后的按钮")
    monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: [1001])
    monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
    monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: win)
    monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
    monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)
    _disable_rule_heal(monkeypatch)

    # LLM 返回修正后的 path(把按钮 name 修正为窗口中的现名)
    fixed = _heal_ele("改名后的按钮")
    fixed_content = json.dumps({"path": fixed["path"]}, ensure_ascii=False)
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse({"code": "0000", "data": fixed_content}),
    )

    report = {}
    res = LocatorManager().locator(_heal_ele("已消失的按钮"), report=report)
    assert res is not None
    assert report["healed"] is True
    assert report["ai_healed"] is True
    assert "AI 修复" in report["repair_hint"]

    metrics = heal_store.metrics_snapshot()
    assert metrics["ai_heal_attempt"] == 1
    assert metrics["ai_heal_success"] == 1

    # 修复结果持久化: 同一元素下次定位走缓存快路径, 不再调 LLM
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _raise(AssertionError("应命中自愈缓存而非再次调 LLM")),
    )
    report2 = {}
    res2 = LocatorManager().locator(_heal_ele("已消失的按钮"), report=report2)
    assert res2 is not None
    assert report2.get("heal_cache") is True
    assert heal_store.metrics_snapshot()["heal_cache_hit"] == 1


def _raise(exc):
    raise exc


def test_manager_AI修复路径验证失败则不吞原错误(monkeypatch):
    """LLM 给出的修正路径仍定位失败时, 保持原定位失败链路(抛出原异常)"""
    from test_uia_heal import _build_win, _ele as _heal_ele
    from astronverse.locator.core import uia_locator as uia_mod
    from astronverse.locator.locator import LocatorManager

    empty_win, _ = _build_win("不相关")
    empty_win._children = []
    monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: [1001])
    monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
    monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: empty_win)
    monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
    monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)

    # 修正路径仍指向不存在的按钮(完整两层: 窗口层命中, 按钮层失配) → 验证失败保持原链路
    fixed_content = json.dumps({"path": _heal_ele("不存在的按钮")["path"]}, ensure_ascii=False)
    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse({"code": "0000", "data": fixed_content}),
    )

    report = {}
    with pytest.raises(Exception):
        LocatorManager().locator(_heal_ele("已消失的按钮"), report=report)
    assert not report.get("ai_healed")


def test_manager_可关闭AI修复(monkeypatch):
    from test_uia_heal import _build_win, _ele as _heal_ele
    from astronverse.locator.core import uia_locator as uia_mod
    from astronverse.locator.locator import LocatorManager

    empty_win, _ = _build_win("不相关")
    empty_win._children = []
    monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: [1001])
    monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
    monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: empty_win)
    monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
    monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)

    monkeypatch.setattr(
        ai_heal_mod.requests,
        "post",
        lambda url, json=None, timeout=None: _raise(AssertionError("关闭时不应调 LLM")),
    )
    with pytest.raises(Exception):
        LocatorManager().locator(_heal_ele("已消失的按钮"), ai_heal=False)


def test_report_tips_AI修复文案():
    from astronverse.locator.core.heal_store import format_report_tips

    tips = format_report_tips({"healed": True, "ai_healed": True, "repair_hint": "元素已通过 AI 修复定位路径并验证成功"})
    assert any("AI 修复" in tip for tip in tips)
    tips = format_report_tips({"ai_healed": True})
    assert any("AI" in tip for tip in tips)
    tips = format_report_tips({"healed": True})
    assert any("自动修复" in tip for tip in tips)
