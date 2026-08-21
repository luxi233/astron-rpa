"""E10 自愈/CV 降级信息回传步骤日志的单测。

覆盖:
1. heal_store.format_report_tips 各 report 键位的提示生成(含无命中空列表)
2. LocatorManager.locator 的 report 回写契约(自愈缓存命中/自愈成功/CV 降级成功/歧义)
"""

import pytest

# 导入即安装 win32/uiautomation/win32com 依赖桩(复用现有套件), 使 locator 包可在非 Windows 平台导入
import test_uia_similar_locator  # noqa: F401

from astronverse.locator import PickerDomain  # noqa: E402
from astronverse.locator.core.heal_store import format_report_tips  # noqa: E402
from astronverse.locator.locator import LocatorManager  # noqa: E402


class TestFormatReportTips:
    def test_空report无提示(self):
        assert format_report_tips({}) == []
        assert format_report_tips(None) == []

    def test_自愈缓存命中(self):
        tips = format_report_tips({"heal_cache": True})
        assert len(tips) == 1 and "自愈缓存" in tips[0]

    def test_自愈成功优先用repair_hint(self):
        tips = format_report_tips({"healed": True, "repair_hint": "放宽 name 匹配后修复"})
        assert tips == ["放宽 name 匹配后修复"]

    def test_自愈成功无hint用默认文案(self):
        tips = format_report_tips({"healed": True})
        assert "已自动修复" in tips[0]

    def test_CV降级成功(self):
        tips = format_report_tips({"cv_fallback": True})
        assert "图像匹配" in tips[0]

    def test_CV歧义(self):
        tips = format_report_tips({"cv_ambiguous": 3})
        assert "3 处" in tips[0] and "重新拾取" in tips[0]

    def test_多状态叠加(self):
        tips = format_report_tips({"healed": True, "repair_hint": "r", "cv_fallback": True})
        assert len(tips) == 2


class TestLocatorReportPassthrough:
    """LocatorManager.locator 的 report 回写契约(与组件层提示链路对接的边界)"""

    def _manager_with_fake_handler(self, monkeypatch, result):
        manager = LocatorManager()
        called = {}

        def fake_callback():
            def _find(ele, picker_type, **kwargs):
                called["kwargs"] = kwargs
                # report 不应透传给定位器回调(仅供上层回写)
                assert "report" not in kwargs
                return result

            return _find

        manager.locator_handler = {PickerDomain.UIA.value: [fake_callback]}
        return manager, called

    def test_report不透传给定位器回调(self, monkeypatch):
        manager, called = self._manager_with_fake_handler(monkeypatch, object())
        report = {}
        res = manager.locator({"type": "uia"}, report=report)
        assert res is not None
        assert "report" not in called["kwargs"]

    def test_自愈缓存命中回写heal_cache(self, monkeypatch):
        from astronverse.locator.core import heal_store

        monkeypatch.setattr(heal_store, "heal_cache_get", lambda ele: [{"name": "fixed"}])
        manager, _ = self._manager_with_fake_handler(monkeypatch, object())
        report = {}
        manager.locator({"type": "uia", "app": "x", "path": []}, report=report)
        assert report.get("heal_cache") is True

    def test_定位成功时report无自愈键位(self, monkeypatch):
        manager, _ = self._manager_with_fake_handler(monkeypatch, object())
        report = {}
        manager.locator({"type": "uia"}, report=report)
        assert format_report_tips(report) == []
