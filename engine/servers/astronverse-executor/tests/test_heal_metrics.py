"""E12 自愈指标聚合回传单测。

merge_heal_metrics: 执行结束时把定位层 heal_store 的运行期指标并入 TASK_END data;
locator 不可用(非 Windows)时静默跳过不阻断收尾。
"""

import sys
import types

from astronverse.executor.debug.debug_svc import merge_heal_metrics


def test_locator可用时并入指标快照(monkeypatch):
    # macOS 无 uiautomation, 用假模块注入模拟 Windows 运行态
    pkg = types.ModuleType("astronverse.locator")
    core = types.ModuleType("astronverse.locator.core")
    heal = types.ModuleType("astronverse.locator.core.heal_store")
    heal.metrics_snapshot = lambda: {"locate_total": 3, "heal_success": 1}
    pkg.core = core
    core.heal_store = heal
    monkeypatch.setitem(sys.modules, "astronverse.locator", pkg)
    monkeypatch.setitem(sys.modules, "astronverse.locator.core", core)
    monkeypatch.setitem(sys.modules, "astronverse.locator.core.heal_store", heal)

    data = {"result": "ok"}
    merge_heal_metrics(data)
    assert data["heal_metrics"] == {"locate_total": 3, "heal_success": 1}
    assert data["result"] == "ok"


def test_指标获取异常时静默跳过(monkeypatch):
    # locator 可用但快照获取异常(或 macOS 上导入失败)均不阻断收尾, 不写入 heal_metrics
    heal = types.ModuleType("astronverse.locator.core.heal_store")

    def _boom():
        raise RuntimeError("snapshot error")

    heal.metrics_snapshot = _boom
    pkg = types.ModuleType("astronverse.locator")
    core = types.ModuleType("astronverse.locator.core")
    pkg.core = core
    core.heal_store = heal
    monkeypatch.setitem(sys.modules, "astronverse.locator", pkg)
    monkeypatch.setitem(sys.modules, "astronverse.locator.core", core)
    monkeypatch.setitem(sys.modules, "astronverse.locator.core.heal_store", heal)

    data = {}
    merge_heal_metrics(data)
    assert "heal_metrics" not in data
