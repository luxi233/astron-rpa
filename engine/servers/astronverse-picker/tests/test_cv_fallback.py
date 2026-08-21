"""E3 元素+图像融合降级回归测试。

覆盖:
1. 元素截图(base64)解码
2. CV 模板匹配命中/未命中
3. cv_fallback 端到端(截图桩 + 元素截图)
4. LocatorManager 集成: 自愈失败后自动 CV 降级
"""

import base64
from io import BytesIO

import numpy as np
import pyautogui
import pytest
from PIL import Image

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from astronverse.locator.core.cv_fallback import CVFallbackLocator, cv_fallback, match_template  # noqa: E402


def _make_scene():
    """构造 100x100 噪声屏幕, 在 (30,40) 处嵌入 20x10 噪声图块作为目标"""
    rng = np.random.default_rng(42)
    screen = rng.integers(0, 255, size=(100, 100, 3), dtype=np.uint8)
    patch = rng.integers(0, 255, size=(10, 20, 3), dtype=np.uint8)
    screen[40:50, 30:50] = patch
    return Image.fromarray(screen), Image.fromarray(patch)


def _img_to_b64(img) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------- 解码与匹配 ----------------


def test_decode_有效截图():
    _, patch = _make_scene()
    from astronverse.locator.core.cv_fallback import _decode_template

    tpl = _decode_template({"self": _img_to_b64(patch)})
    assert tpl is not None and tpl.size == (20, 10)


def test_decode_无截图或非法数据():
    from astronverse.locator.core.cv_fallback import _decode_template

    assert _decode_template({}) is None
    assert _decode_template({"self": "not-a-valid-base64-image"}) is None


def test_match_命中返回区域与置信度():
    screen, patch = _make_scene()
    match = match_template(screen, patch, similarity=0.95)
    assert match is not None
    rect, score = match
    assert score >= 0.99
    assert (rect.left, rect.top, rect.right, rect.bottom) == (30, 40, 50, 50)


def test_match_未命中返回None():
    screen, patch = _make_scene()
    # 换一块完全不同的模板
    other = Image.fromarray(np.full((10, 20, 3), 128, dtype=np.uint8))
    assert match_template(screen, other, similarity=0.95) is None


# ---------------- 多尺度与歧义 ----------------


def test_match_candidates_跨尺度去重单一命中():
    from astronverse.locator.core.cv_fallback import match_template_candidates

    screen, patch = _make_scene()
    # 原尺寸命中后, 相邻尺度的重合候选应被 IoU 去重为单一结果
    cands = match_template_candidates(screen, patch, similarity=0.95, scales=(1.0, 0.9, 1.1))
    assert len(cands) == 1
    rect, score, scale = cands[0]
    assert scale == 1.0
    assert (rect.left, rect.top) == (30, 40)


def test_match_candidates_缩放模板多尺度命中():
    from astronverse.locator.core.cv_fallback import match_template_candidates

    screen, patch = _make_scene()  # 屏幕嵌入原尺寸 20x10
    big = patch.resize((24, 12), Image.NEAREST)  # 模拟 DPI 放大后拾取的截图
    # 原尺寸必然失配, 缩回 5/6(24→20, 12→10)精确还原后命中
    cands = match_template_candidates(screen, big, similarity=0.95, scales=(1.0, 5 / 6))
    assert cands
    rect, score, scale = cands[0]
    assert scale == pytest.approx(5 / 6)
    assert score >= 0.99
    assert (rect.left, rect.top) == (30, 40)


def test_fallback_多处命中歧义中止(monkeypatch):
    rng = np.random.default_rng(7)
    screen_arr = rng.integers(0, 255, size=(100, 100, 3), dtype=np.uint8)
    patch = rng.integers(0, 255, size=(10, 20, 3), dtype=np.uint8)
    # 同一图块嵌入两处相距较远的位置 → 歧义
    screen_arr[10:20, 5:25] = patch
    screen_arr[70:80, 60:80] = patch
    screen = Image.fromarray(screen_arr)
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)
    # 歧义时放弃降级(避免误点), 返回 None; 候选数回写 report 供上层提示
    report = {}
    assert cv_fallback({"img": {"self": _img_to_b64(Image.fromarray(patch))}}, report=report) is None
    assert report.get("cv_ambiguous") == 2


def test_fallback_歧义回传候选列表(monkeypatch):
    """I1: 歧义时 report 一并回传候选(rect+置信度), 供交互式消歧"""
    rng = np.random.default_rng(7)
    screen_arr = rng.integers(0, 255, size=(100, 100, 3), dtype=np.uint8)
    patch = rng.integers(0, 255, size=(10, 20, 3), dtype=np.uint8)
    screen_arr[10:20, 5:25] = patch
    screen_arr[70:80, 60:80] = patch
    screen = Image.fromarray(screen_arr)
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)
    report = {}
    assert cv_fallback({"img": {"self": _img_to_b64(Image.fromarray(patch))}}, report=report) is None
    cands = report["cv_candidates"]
    assert len(cands) == 2
    for cand in cands:
        assert len(cand["rect"]) == 4
        assert cand["score"] >= 0.95
    rects = sorted(c["rect"] for c in cands)
    assert rects == [[5, 10, 25, 20], [60, 70, 80, 80]]


def test_disambiguate_按选定候选构造坐标定位器():
    from astronverse.locator.core.cv_fallback import cv_disambiguate

    loc = cv_disambiguate([60, 70, 80, 80])
    assert isinstance(loc, CVFallbackLocator)
    rect = loc.rect()
    assert (rect.left, rect.top, rect.right, rect.bottom) == (60, 70, 80, 80)
    assert loc.control() is None


def test_fallback_多尺度端到端命中(monkeypatch):
    screen, patch = _make_scene()
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)
    big = patch.resize((24, 12), Image.NEAREST)
    ele = {"img": {"self": _img_to_b64(big)}}
    # 默认尺度序列含 5/6, 无需降阈即可命中
    loc = cv_fallback(ele)
    assert isinstance(loc, CVFallbackLocator)
    rect = loc.rect()
    assert (rect.left, rect.top) == (30, 40)


# ---------------- cv_fallback 端到端 ----------------


def test_fallback_命中返回坐标定位器(monkeypatch):
    screen, patch = _make_scene()
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)
    ele = {"img": {"self": _img_to_b64(patch)}}
    loc = cv_fallback(ele)
    assert isinstance(loc, CVFallbackLocator)
    rect = loc.rect()
    assert (rect.left, rect.top) == (30, 40)
    assert loc.control() is None


def test_fallback_无截图直接跳过(monkeypatch):
    monkeypatch.setattr(pyautogui, "screenshot", lambda: (_ for _ in ()).throw(AssertionError("不应截图")))
    assert cv_fallback({}) is None
    assert cv_fallback({"img": {}}) is None


def test_fallback_屏幕不含目标返回None(monkeypatch):
    _, patch = _make_scene()
    blank = Image.fromarray(np.full((100, 100, 3), 200, dtype=np.uint8))
    monkeypatch.setattr(pyautogui, "screenshot", lambda: blank)
    assert cv_fallback({"img": {"self": _img_to_b64(patch)}}) is None


# ---------------- LocatorManager 集成 ----------------


def test_manager_定位与自愈失败后CV降级命中(monkeypatch):
    from test_uia_heal import _build_win, _ele
    from astronverse.locator.core import uia_locator as _m

    empty_win, _ = _build_win("不相关")
    empty_win._children = []
    monkeypatch.setattr(_m, "find_window_handles_list", lambda *a, **k: [1001])
    monkeypatch.setattr(_m, "find_window_by_enum_list", lambda *a, **k: [])
    monkeypatch.setattr(_m, "ControlFromHandle", lambda handle: empty_win)
    monkeypatch.setattr(_m, "validate_window_rect", lambda *a, **k: True)
    monkeypatch.setattr(_m, "is_desktop_by_handle", lambda *a, **k: False)

    screen, patch = _make_scene()
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)

    from astronverse.locator.locator import LocatorManager

    ele = _ele("已消失的按钮")
    ele["img"] = {"self": _img_to_b64(patch)}
    res = LocatorManager().locator(ele)
    assert isinstance(res, CVFallbackLocator)
    assert (res.rect().left, res.rect().top) == (30, 40)


def test_manager_可关闭CV降级(monkeypatch):
    from test_uia_heal import _build_win, _ele
    from astronverse.locator.core import uia_locator as _m

    empty_win, _ = _build_win("不相关")
    empty_win._children = []
    monkeypatch.setattr(_m, "find_window_handles_list", lambda *a, **k: [1001])
    monkeypatch.setattr(_m, "find_window_by_enum_list", lambda *a, **k: [])
    monkeypatch.setattr(_m, "ControlFromHandle", lambda handle: empty_win)
    monkeypatch.setattr(_m, "validate_window_rect", lambda *a, **k: True)
    monkeypatch.setattr(_m, "is_desktop_by_handle", lambda *a, **k: False)

    from astronverse.locator.locator import LocatorManager

    screen, patch = _make_scene()
    monkeypatch.setattr(pyautogui, "screenshot", lambda: screen)
    ele = _ele("已消失的按钮")
    ele["img"] = {"self": _img_to_b64(patch)}
    with pytest.raises(Exception):
        LocatorManager().locator(ele, cv_fallback=False)
