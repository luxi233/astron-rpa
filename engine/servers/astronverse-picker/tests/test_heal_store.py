"""自愈持久化 + 可观测性 + 批量校验回归测试。

覆盖:
1. heal_store 缓存读写/淘汰/失效移除
2. heal_store 指标计数与耗时记录
3. LocatorManager 缓存快路径(免重复自愈) + 缓存失效回退重新自愈
4. report 回写自愈信息(校验链路前端提示来源)
5. WS BATCH_VALIDATE 批量校验报告
6. WS PICKER_METRICS 指标查询 / WS HEAL_CACHE_DROP 单条缓存清理
7. WS CONTROL_TREE pick 分支(树点选拾取元素构造)
"""

import json
import sys

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from test_uia_heal import FakeControl, _build_win, _ele  # noqa: E402
from test_ws_server import _FakeSvc, _make_mod, _run  # noqa: E402
from astronverse.locator.core import heal_store  # noqa: E402
from astronverse.locator.core import uia_locator as uia_mod  # noqa: E402
from astronverse.picker import PickerSign  # noqa: E402
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire  # noqa: E402


@pytest.fixture()
def patch_env(monkeypatch):
    def _patch(win):
        monkeypatch.setattr(uia_mod, "find_window_handles_list", lambda *a, **k: [1001])
        monkeypatch.setattr(uia_mod, "find_window_by_enum_list", lambda *a, **k: [])
        monkeypatch.setattr(uia_mod, "ControlFromHandle", lambda handle: win)
        monkeypatch.setattr(uia_mod, "validate_window_rect", lambda *a, **k: True)
        monkeypatch.setattr(uia_mod, "is_desktop_by_handle", lambda *a, **k: False)

    return _patch


# ---------------- heal_store 缓存 ----------------


def test_cache_put_get往返():
    ele = {"app": "app", "path": [{"tag_name": "WindowControl"}]}
    healed = [{"tag_name": "WindowControl", "disable_keys": ["name"]}]
    assert heal_store.heal_cache_get(ele) is None
    heal_store.heal_cache_put(ele, healed, ["第1层放宽name/value"])
    assert heal_store.heal_cache_get(ele) == healed
    # 全部条目可查询
    entries = heal_store.heal_cache_all()
    assert len(entries) == 1
    entry = list(entries.values())[0]
    assert entry["relaxations"] == ["第1层放宽name/value"]


def test_cache_drop移除():
    ele = {"app": "app", "path": [{"tag_name": "X"}]}
    heal_store.heal_cache_put(ele, [], [])
    heal_store.heal_cache_drop(ele)
    assert heal_store.heal_cache_get(ele) is None


def test_cache_drop_key按键删除():
    ele = {"app": "app", "path": [{"tag_name": "Y"}]}
    heal_store.heal_cache_put(ele, [{"tag_name": "Y"}], ["放宽"])
    key = heal_store.element_cache_key(ele)
    assert heal_store.heal_cache_drop_key(key) is True
    assert heal_store.heal_cache_get(ele) is None
    # 重复删除返回 False
    assert heal_store.heal_cache_drop_key(key) is False


def test_cache_超上限淘汰最旧(monkeypatch):
    monkeypatch.setattr(heal_store, "HEAL_CACHE_MAX_ENTRIES", 2)
    for i in range(3):
        heal_store.heal_cache_put({"app": f"app{i}", "path": [{"i": i}]}, [{"i": i}], [])
    entries = heal_store.heal_cache_all()
    assert len(entries) == 2
    # 最旧(app0)被淘汰
    assert all(v["app"] != "app0" for v in entries.values())


def test_cache_损坏文件按空缓存处理(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRON_HEAL_CACHE", str(tmp_path / "bad.json"))
    (tmp_path / "bad.json").write_text("not-json", encoding="utf-8")
    assert heal_store.heal_cache_get({"app": "a", "path": []}) is None


# ---------------- 指标 ----------------


def test_metrics计数与快照():
    heal_store.record_metric("heal_attempt")
    heal_store.record_metric("heal_attempt")
    heal_store.record_metric("未知事件")  # 忽略
    heal_store.record_timing(12.345)
    snap = heal_store.metrics_snapshot()
    assert snap["heal_attempt"] == 2
    assert snap["last_locate_ms"] == 12.3
    heal_store.reset_metrics()
    assert heal_store.metrics_snapshot()["heal_attempt"] == 0


# ---------------- LocatorManager 缓存快路径 ----------------


def test_manager自愈成功后二次定位走缓存(patch_env):
    from astronverse.locator.locator import LocatorManager

    win, button = _build_win("新名称")
    patch_env(win)
    ele = _ele("旧名称")

    report1 = {}
    res1 = LocatorManager().locator(ele, report=report1)
    assert res1.control() is button
    assert report1.get("healed") is True
    assert report1["relaxations"] == ["第2层放宽name/value"]
    assert heal_store.metrics_snapshot()["heal_success"] == 1

    # 第二次: 缓存快路径命中, 不再触发自愈探索
    report2 = {}
    res2 = LocatorManager().locator(ele, report=report2)
    assert res2.control() is button
    assert report2.get("heal_cache") is True
    assert "healed" not in report2
    assert heal_store.metrics_snapshot()["heal_cache_hit"] == 1
    assert heal_store.metrics_snapshot()["heal_attempt"] == 1  # 仅首次探索


def test_manager缓存失效自动移除并重新自愈(patch_env):
    from astronverse.locator.locator import LocatorManager

    win, _ = _build_win("名称A")
    patch_env(win)
    ele = _ele("旧名称")
    LocatorManager().locator(ele)  # 首次自愈并写缓存
    assert heal_store.heal_cache_get(ele) is not None

    # UI 再次变化: cls 也变了, 缓存的修复版(仅放宽 name)也失效 → 移除缓存 → 重新自愈
    win2 = FakeControl("WindowControl", cls="AppWin", name="Doc1", handle=1001)
    button2 = FakeControl("ButtonControl", cls="RenamedCtl", name="名称B")
    win2._children = [button2]
    button2._parent = win2
    patch_env(win2)
    report = {}
    res = LocatorManager().locator(ele, report=report)
    assert res.control() is button2
    assert heal_store.metrics_snapshot()["heal_cache_invalidated"] == 1
    assert report.get("healed") is True


def test_manager_similar与picker_type不走自愈缓存(patch_env):
    from astronverse.locator.locator import LocatorManager

    win, _ = _build_win("同名")
    patch_env(win)
    ele = _ele("同名")
    ele["picker_type"] = "SIMILAR"
    heal_store.heal_cache_put(ele, [{"伪造": True}], [])
    # picker_type 非空 → 不走缓存快路径(缓存条目不应生效)
    report = {}
    try:
        LocatorManager().locator(ele, report=report)
    except Exception:
        pass
    assert "heal_cache" not in report


# ---------------- WS BATCH_VALIDATE ----------------


class _BatchFakeLocator:
    def __init__(self, ctrl):
        self._ctrl = ctrl

    def control(self):
        return self._ctrl


class _BatchFakeManager:
    """可编程的 LocatorManager 桩: 按元素 name 决定成功/自愈/失败"""

    def locator(self, element, **kwargs):
        report = kwargs.get("report")
        ele = json.loads(element) if isinstance(element, str) else element
        name = ele.get("path", [{}])[-1].get("name", "")
        if name == "好的":
            return _BatchFakeLocator(object())
        if name == "自愈的":
            if isinstance(report, dict):
                report["healed"] = True
            return _BatchFakeLocator(object())
        if name == "歧义的":
            # I1: 模拟 CV 降级歧义中止(定位返回 None + 候选回写 report)
            if isinstance(report, dict):
                report["cv_ambiguous"] = 2
                report["cv_candidates"] = [
                    {"rect": [5, 10, 25, 20], "score": 0.99},
                    {"rect": [60, 70, 80, 80], "score": 0.97},
                ]
            return None
        raise Exception("元素定位失败")


def test_ws_BATCH_VALIDATE逐项报告(monkeypatch):
    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_BatchFakeManager))
    handler = PickerRequestHandler(_FakeSvc())
    items = [
        {"id": "1", "name": "确定按钮", "element": {"path": [{"name": "好的"}]}},
        {"id": "2", "name": "改名输入框", "element": {"path": [{"name": "自愈的"}]}},
        {"id": "3", "name": "消失按钮", "element": {"path": [{"name": "没了"}]}},
    ]
    req = PickerRequire(pick_sign=PickerSign.BATCH_VALIDATE, data=json.dumps(items))
    result = _run(handler._handle_batch_validate(req))
    assert result["success"] is True
    records = json.loads(result["data"])
    assert [r["success"] for r in records] == [True, True, False]
    assert records[1]["note"] == "已自动修复"
    assert "元素定位失败" in records[2]["error"]


def test_ws_BATCH_VALIDATE非数组报错():
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.BATCH_VALIDATE, data=json.dumps({"not": "list"}))
    result = _run(handler._handle_batch_validate(req))
    assert result["success"] is False
    assert "数组" in result["error"]


def test_ws_BATCH_VALIDATE歧义回传候选(monkeypatch):
    """I1: CV 歧义失败项携带 cv_candidates 供前端交互式消歧"""
    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_BatchFakeManager))
    handler = PickerRequestHandler(_FakeSvc())
    items = [{"id": "1", "name": "重复按钮", "element": {"path": [{"name": "歧义的"}]}}]
    req = PickerRequire(pick_sign=PickerSign.BATCH_VALIDATE, data=json.dumps(items))
    result = _run(handler._handle_batch_validate(req))
    assert result["success"] is True
    records = json.loads(result["data"])
    assert records[0]["success"] is False
    assert "可选定候选" in records[0]["error"]
    assert len(records[0]["cv_candidates"]) == 2
    assert records[0]["cv_candidates"][0]["rect"] == [5, 10, 25, 20]


def test_ws_BATCH_VALIDATE并行保序与计数(monkeypatch):
    """L2: 多元素并行校验保序/计数正确, 且真实分布在多个工作线程"""
    import threading
    import time

    seen_threads = set()

    class _ConcurrentManager:
        def locator(self, element, **kwargs):
            seen_threads.add(threading.get_ident())
            time.sleep(0.02)  # 模拟定位耗时, 串行总时长会明显大于并行
            ele = json.loads(element) if isinstance(element, str) else element
            name = ele.get("path", [{}])[-1].get("name", "")
            if name == "fail":
                raise Exception("定位失败")
            return _BatchFakeLocator(object())

    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_ConcurrentManager))
    handler = PickerRequestHandler(_FakeSvc())
    items = [
        {"id": str(i), "name": f"元素{i}", "element": {"path": [{"name": "fail" if i % 3 == 2 else "ok"}]}}
        for i in range(9)
    ]
    req = PickerRequire(pick_sign=PickerSign.BATCH_VALIDATE, data=json.dumps(items))
    result = _run(handler._handle_batch_validate(req))
    assert result["success"] is True
    records = json.loads(result["data"])
    # 保序: 结果 id 与输入一致; 计数: 成功/失败分布与预期一致
    assert [r["id"] for r in records] == [str(i) for i in range(9)]
    assert [r["success"] for r in records] == [i % 3 != 2 for i in range(9)]
    assert "定位失败" in records[2]["error"]
    # 确认真实并发执行(多工作线程)
    assert len(seen_threads) >= 2


# ---------------- WS CV_DISAMBIGUATE ----------------


def test_ws_CV_DISAMBIGUATE选定候选返回坐标():
    handler = PickerRequestHandler(_FakeSvc())
    data = {"id": "1", "name": "重复按钮", "rect": [60, 70, 80, 80], "score": 0.97}
    req = PickerRequire(pick_sign=PickerSign.CV_DISAMBIGUATE, data=json.dumps(data))
    result = _run(handler._handle_cv_disambiguate(req))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["success"] is True
    assert payload["rect"] == [60, 70, 80, 80]
    assert payload["center"] == [70, 75]
    assert payload["score"] == 0.97


def test_ws_CV_DISAMBIGUATE非法rect报错():
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.CV_DISAMBIGUATE, data=json.dumps({"rect": [1, 2]}))
    result = _run(handler._handle_cv_disambiguate(req))
    assert result["success"] is False
    assert "rect" in result["error"]


# ---------------- WS PICKER_METRICS ----------------


def test_ws_PICKER_METRICS返回指标与缓存():
    heal_store.record_metric("locate_total")
    heal_store.heal_cache_put({"app": "m", "path": [1]}, [2], ["放宽"])
    handler = PickerRequestHandler(_FakeSvc())
    result = _run(handler._handle_picker_metrics(PickerRequire(pick_sign=PickerSign.PICKER_METRICS)))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["metrics"]["locate_total"] == 1
    assert len(payload["heal_cache"]) == 1


# ---------------- WS HEAL_CACHE_DROP ----------------


def test_ws_HEAL_CACHE_DROP按键删除():
    ele = {"app": "drop", "path": [{"tag_name": "Z"}]}
    heal_store.heal_cache_put(ele, [{"tag_name": "Z"}], ["放宽"])
    key = heal_store.element_cache_key(ele)
    handler = PickerRequestHandler(_FakeSvc())
    result = _run(
        handler._handle_heal_cache_drop(PickerRequire(pick_sign=PickerSign.HEAL_CACHE_DROP, data=key))
    )
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload == {"key": key, "dropped": True}
    assert heal_store.heal_cache_get(ele) is None


def test_ws_HEAL_CACHE_DROP不存在的键():
    handler = PickerRequestHandler(_FakeSvc())
    result = _run(
        handler._handle_heal_cache_drop(PickerRequire(pick_sign=PickerSign.HEAL_CACHE_DROP, data="no-such-key"))
    )
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["dropped"] is False


# ---------------- WS CONTROL_TREE 树点选拾取 ----------------


def test_ws_CONTROL_TREE_pick构造元素并验证(monkeypatch):
    class _TreeFakeManager:
        def __init__(self):
            self.received = None

        def locator(self, element, **kwargs):
            self.received = (element, kwargs)
            return _BatchFakeLocator(object())

    mgr = _TreeFakeManager()
    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=lambda: mgr))
    handler = PickerRequestHandler(_FakeSvc())
    chain = [
        {"tag_name": "WindowControl", "cls": "AppWin", "name": "Doc1", "automation_id": None},
        {"tag_name": "ButtonControl", "cls": "BtnCtl", "name": "确定", "automation_id": "okBtn"},
    ]
    req = PickerRequire(pick_sign=PickerSign.CONTROL_TREE, ext_data={"pick": chain})
    result = _run(handler._handle_control_tree(req))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["located"] is True
    ele = payload["element"]
    assert ele["type"] == "uia"
    assert ele["app"] == "Doc1"  # 窗口层名称作为分组名
    assert len(ele["path"]) == 2
    assert ele["path"][1]["automation_id"] == "okBtn"
    # 树点选验证不允许触发自愈/CV 降级(避免构造出的元素被意外放宽)
    assert mgr.received[1].get("self_heal") is False
    assert mgr.received[1].get("cv_fallback") is False


def test_ws_CONTROL_TREE_pick定位失败仍返回元素(monkeypatch):
    class _FailManager:
        def locator(self, element, **kwargs):
            raise Exception("定位失败")

    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=lambda: _FailManager()))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(
        pick_sign=PickerSign.CONTROL_TREE, ext_data={"pick": [{"tag_name": "ButtonControl", "name": "x"}]}
    )
    result = _run(handler._handle_control_tree(req))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert payload["located"] is False
    assert payload["element"]["path"][0]["name"] == "x"
