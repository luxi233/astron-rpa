"""相似元素执行端定位契约(E11)。

WebFactory.find 对相似元素(多命中)的承载契约: 返回单个 WEBLocator,
rect() 在多命中时返回 rects 列表(调用方据此判定"定位不唯一"或遍历操作),
单命中时返回单个 Rect; picker_type 不参与 web 定位分发。
本测试固化该契约, 避免前端选择器/原子遍历行为因定位层改动而失据。
"""

import pytest

# 导入即安装 win32/uiautomation/win32com 依赖桩(复用现有套件), 使 locator 包可在非 Windows 平台导入
import test_uia_similar_locator  # noqa: F401

from astronverse.locator import Rect  # noqa: E402
from astronverse.locator.core.web_locator import WEBLocator, WebFactory  # noqa: E402


def _rect(x, y, right, bottom) -> dict:
    return {"x": x, "y": y, "right": right, "bottom": bottom}


def _patch(monkeypatch, rect_res, menu_height=0, menu_left=0):
    # 尾部双下划线方法不触发 name mangling, 直接用原名
    monkeypatch.setattr(WebFactory, "__get_web_top__", classmethod(lambda cls, ele, app: (menu_height, menu_left)))
    monkeypatch.setattr(
        WebFactory,
        "__get_rect_from_browser_plugin__",
        classmethod(lambda cls, ele, app, scroll_into_view=True, scroll_into_center=True: rect_res),
    )


class TestWebFindContract:
    def test_单命中rect返回单Rect(self, monkeypatch):
        _patch(monkeypatch, [_rect(10, 20, 30, 40)])
        res = WebFactory.find(ele={"app": "chrome"}, picker_type="")
        assert isinstance(res, WEBLocator)
        rect = res.rect()
        assert isinstance(rect, Rect)
        assert (rect.left, rect.top, rect.right, rect.bottom) == (10, 20, 30, 40)

    def test_多命中rect返回列表(self, monkeypatch):
        # 相似元素: 插件返回多个 rect, rect() 返回 rects 列表供上层遍历/判不唯一
        _patch(monkeypatch, [_rect(0, 0, 10, 10), _rect(20, 20, 30, 30), _rect(40, 40, 50, 50)])
        res = WebFactory.find(ele={"app": "chrome"}, picker_type="")
        rect = res.rect()
        assert isinstance(rect, list) and len(rect) == 3
        assert all(isinstance(r, Rect) for r in rect)

    def test_多命中坐标应用窗口偏移(self, monkeypatch):
        _patch(monkeypatch, [_rect(0, 0, 10, 10), _rect(5, 5, 15, 15)], menu_height=100, menu_left=7)
        res = WebFactory.find(ele={"app": "chrome"}, picker_type="")
        rects = res.rect()
        assert (rects[0].left, rects[0].top) == (7, 100)
        assert (rects[1].right, rects[1].bottom) == (15 + 7, 15 + 100)

    def test_SIMILAR类型与普通定位返回形态一致(self, monkeypatch):
        # picker_type 不影响 web 定位分发: 相似元素靠 rects 多值承载
        _patch(monkeypatch, [_rect(0, 0, 10, 10), _rect(20, 20, 30, 30)])
        res_similar = WebFactory.find(ele={"app": "chrome"}, picker_type="SIMILAR")
        res_normal = WebFactory.find(ele={"app": "chrome"}, picker_type="")
        assert isinstance(res_similar.rect(), list) == isinstance(res_normal.rect(), list)
        assert len(res_similar.rect()) == len(res_normal.rect())

    def test_非Chrome内核应用直接返回None(self, monkeypatch):
        _patch(monkeypatch, [_rect(0, 0, 10, 10)])
        assert WebFactory.find(ele={"app": "not_a_browser"}, picker_type="") is None

    def test_插件无结果返回None(self, monkeypatch):
        _patch(monkeypatch, [])
        assert WebFactory.find(ele={"app": "chrome"}, picker_type="") is None

    def test_cur_target_app覆盖元素app(self, monkeypatch):
        # 元素 app 非浏览器但运行态指定了浏览器类型时仍可定位
        _patch(monkeypatch, [_rect(0, 0, 10, 10)])
        res = WebFactory.find(ele={"app": "unknown"}, picker_type="", cur_target_app="chrome")
        assert isinstance(res, WEBLocator)


class TestWEBLocatorShape:
    def test_rects为空时回退单rect(self):
        loc = WEBLocator(rect=Rect(1, 2, 3, 4), rects=[])
        assert isinstance(loc.rect(), Rect)

    def test_control恒为None(self):
        assert WEBLocator(rect=Rect(1, 2, 3, 4)).control() is None
