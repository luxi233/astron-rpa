"""E4 虚拟列表批量采集回归测试。

覆盖:
1. 滚动分批续采与跨屏去重
2. max_scrolls 上限/到底停止/滚动无新增停止
3. 空属性条目按 rect 指纹去重
4. item 过滤函数
5. 默认 ScrollPattern 滚动实现(前进/到底/不支持)
6. ws 命令 VIRTUAL_LIST 路由
"""

import json
import sys
from types import SimpleNamespace

import pytest

from astronverse.picker import PickerSign
from astronverse.picker.core.virtual_list import collect_virtual_list, default_scroll, item_fingerprint
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire

from test_ws_server import _FakeSvc, _run  # noqa: E402


class FakeItem:
    """虚拟列表条目桩"""

    def __init__(self, name, tag="ListItemControl", cls="Item", automation_id=None, rect=(0, 0, 10, 10)):
        self.ControlTypeName = tag
        self.ClassName = cls
        self.Name = name
        if automation_id is not None:
            self.AutomationId = automation_id
        self.BoundingRectangle = SimpleNamespace(left=rect[0], top=rect[1], right=rect[2], bottom=rect[3])

    def GetChildren(self):
        return []


class FakeContainer:
    """按页滚动容器桩: pages[i] 为第 i 屏的条目列表"""

    def __init__(self, pages):
        self.pages = pages
        self.page = 0
        self.scroll_calls = 0

    def GetChildren(self):
        return self.pages[self.page] if self.page < len(self.pages) else []

    def scroll(self, container):
        self.scroll_calls += 1
        if self.page >= len(self.pages) - 1:
            return False
        self.page += 1
        return True


def _names(items):
    return [i.Name for i in items]


# ---------------- 采集核心 ----------------


def test_分批续采跨屏去重():
    a, b, c, d = FakeItem("A"), FakeItem("B"), FakeItem("C"), FakeItem("D")
    container = FakeContainer([[a, b], [b, c], [c, d]])
    items = collect_virtual_list(container, scroll_fn=container.scroll)
    assert _names(items) == ["A", "B", "C", "D"]
    assert container.scroll_calls == 3  # 末屏后需再滚一次探底才停止


def test_max_scrolls上限():
    container = FakeContainer([[FakeItem("A")], [FakeItem("B")], [FakeItem("C")], [FakeItem("D")]])
    items = collect_virtual_list(container, scroll_fn=container.scroll, max_scrolls=1)
    assert _names(items) == ["A", "B"]
    assert container.scroll_calls == 1


def test_滚动到底提前停止():
    container = FakeContainer([[FakeItem("A")], [FakeItem("B")]])
    items = collect_virtual_list(container, scroll_fn=container.scroll, max_scrolls=10)
    assert _names(items) == ["A", "B"]
    assert container.scroll_calls == 2  # 第二次滚动返回 False 即到底


def test_滚动后无新增停止():
    container = FakeContainer([[FakeItem("A")], [FakeItem("A")], [FakeItem("B")]])
    items = collect_virtual_list(container, scroll_fn=container.scroll)
    assert _names(items) == ["A"]
    assert container.scroll_calls == 2  # 第二屏无新增, 滚动后判定完成


def test_空属性条目按rect去重():
    p1 = FakeItem("", rect=(0, 0, 10, 10))
    p2 = FakeItem("", rect=(0, 10, 10, 20))
    p1_dup = FakeItem("", rect=(0, 0, 10, 10))
    container = FakeContainer([[p1], [p1_dup, p2]])
    items = collect_virtual_list(container, scroll_fn=container.scroll)
    assert len(items) == 2  # p1_dup 与 p1 指纹相同被去重


def test_is_item过滤():
    container = FakeContainer(
        [[FakeItem("A", tag="ListItemControl"), FakeItem("头部", tag="TextControl")]]
    )
    items = collect_virtual_list(
        container, is_item=lambda c: c.ControlTypeName == "ListItemControl", scroll_fn=container.scroll
    )
    assert _names(items) == ["A"]


def test_容器None报错():
    with pytest.raises(Exception, match="未获取到容器控件"):
        collect_virtual_list(None)


def test_指纹_名称优先与rect退化():
    named = FakeItem("X", automation_id="idX")
    assert item_fingerprint(named)[-2:] == ("X", "idX")
    blank = FakeItem("")
    assert item_fingerprint(blank)[2] == "rect"


# ---------------- 默认 ScrollPattern 滚动 ----------------


class FakeScrollPattern:
    def __init__(self, percents):
        self._percents = percents
        self._idx = 0

    @property
    def CurrentVerticalScrollPercent(self):
        return self._percents[min(self._idx, len(self._percents) - 1)]

    def Scroll(self, h, v):
        self._idx += 1


def test_default_scroll前进(monkeypatch):
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ScrollAmount", SimpleNamespace(NoAmount=0, LargeIncrement=1), raising=False)
    container = SimpleNamespace(GetScrollPattern=lambda: FakeScrollPattern([0.0, 50.0]))
    assert default_scroll(container) is True


def test_default_scroll到底(monkeypatch):
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ScrollAmount", SimpleNamespace(NoAmount=0, LargeIncrement=1), raising=False)
    container = SimpleNamespace(GetScrollPattern=lambda: FakeScrollPattern([100.0, 100.0]))
    assert default_scroll(container) is False


def test_default_scroll不支持():
    container = SimpleNamespace(GetScrollPattern=lambda: None)
    assert default_scroll(container) is False


# ---------------- 滚轮兜底滚动 ----------------


class _FakePyAutoGui:
    """滚轮事件桩: 记录调用, 可模拟滚动生效/无效"""

    def __init__(self):
        self.calls = []

    def moveTo(self, x, y):
        self.calls.append(("move", x, y))

    def scroll(self, amount):
        self.calls.append(("scroll", amount))

    def hotkey(self, *keys, **kw):
        self.calls.append(("hotkey", keys, kw))


def _wheel_container(pages):
    container = FakeContainer(pages)
    container.BoundingRectangle = SimpleNamespace(left=0, top=0, right=100, bottom=200)
    container.GetScrollPattern = lambda: None  # 不支持 ScrollPattern, 逼走滚轮兜底
    return container


def test_滚轮兜底滚动生效(monkeypatch):
    fake_pg = _FakePyAutoGui()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pg)
    container = _wheel_container([[FakeItem("A")], [FakeItem("B")]])

    def _wheel_side_effect(container_arg):
        # 模拟滚轮事件后翻屏(首条目指纹变化)
        container.page += 1

    fake_pg.scroll = lambda amount: (_wheel_side_effect(container), fake_pg.calls.append(("scroll", amount)))
    assert default_scroll(container) is True
    assert ("move", 50, 100) in fake_pg.calls  # 滚轮发到容器中心


def test_滚轮兜底滚动无变化判到底(monkeypatch):
    fake_pg = _FakePyAutoGui()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pg)
    container = _wheel_container([[FakeItem("A")]])  # 滚动后首条目不变
    assert default_scroll(container) is False


def test_滚轮兜底_依赖缺失返回False(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyautogui", None)  # import 报 ImportError
    container = _wheel_container([[FakeItem("A")], [FakeItem("B")]])
    assert default_scroll(container) is False


# ---------------- 横向滚动 ----------------


class FakeHScrollPattern(FakeScrollPattern):
    def __init__(self, percents, scrollable=True):
        super().__init__(percents)
        self.CurrentHorizontallyScrollable = scrollable

    @property
    def CurrentHorizontalScrollPercent(self):
        return self._percents[min(self._idx, len(self._percents) - 1)]


def test_default_scroll横向前进(monkeypatch):
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ScrollAmount", SimpleNamespace(NoAmount=0, LargeIncrement=1), raising=False)
    container = SimpleNamespace(GetScrollPattern=lambda: FakeHScrollPattern([0.0, 50.0]))
    assert default_scroll(container, horizontal=True) is True


def test_default_scroll横向到底(monkeypatch):
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ScrollAmount", SimpleNamespace(NoAmount=0, LargeIncrement=1), raising=False)
    container = SimpleNamespace(GetScrollPattern=lambda: FakeHScrollPattern([100.0, 100.0]))
    assert default_scroll(container, horizontal=True) is False


def test_default_scroll横向不可滚退滚轮(monkeypatch):
    fake_pg = _FakePyAutoGui()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pg)
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ScrollAmount", SimpleNamespace(NoAmount=0, LargeIncrement=1), raising=False)
    container = _wheel_container([[FakeItem("A")], [FakeItem("B")]])
    container.GetScrollPattern = lambda: FakeHScrollPattern([0.0], scrollable=False)

    def _advance(_):
        container.page += 1

    fake_pg.hotkey = lambda *keys, **kw: (_advance(container), fake_pg.calls.append(("hotkey", keys)))
    assert default_scroll(container, horizontal=True) is True
    assert any(c[0] == "hotkey" for c in fake_pg.calls)  # shift+滚轮模拟横向


def test_collect_horizontal参数走默认滚动(monkeypatch):
    """collect_virtual_list(horizontal=True) 将方向传给默认滚动实现"""
    received = []
    a, b = FakeItem("A"), FakeItem("B")
    container = FakeContainer([[a], [b]])
    import astronverse.picker.core.virtual_list as vl

    monkeypatch.setattr(vl, "default_scroll", lambda c, horizontal=False: (received.append(horizontal), container.scroll(c))[1])
    items = collect_virtual_list(container, horizontal=True)
    assert _names(items) == ["A", "B"]
    assert all(r is True for r in received)


# ---------------- WS 命令路由 ----------------


def test_ws_VIRTUAL_LIST采集成功(monkeypatch):
    import astronverse.picker.core.virtual_list as vl

    a, b, c, d = FakeItem("A"), FakeItem("B"), FakeItem("C"), FakeItem("D")
    container = FakeContainer([[a, b], [b, c], [c, d]])
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ControlFromHandle", lambda handle: container, raising=False)
    # 默认滚动实现签名含 horizontal, 测试桩包装一层
    monkeypatch.setattr(vl, "default_scroll", lambda c, horizontal=False: container.scroll(c))
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VIRTUAL_LIST, ext_data={"handle": 1001, "max_scrolls": 5})
    result = _run(handler._handle_virtual_list(req))
    assert result["success"] is True
    payload = json.loads(result["data"])
    assert [node["name"] for node in payload] == ["A", "B", "C", "D"]


def test_ws_VIRTUAL_LIST按tag过滤(monkeypatch):
    a = FakeItem("A", tag="ListItemControl")
    header = FakeItem("头部", tag="TextControl")
    container = FakeContainer([[a, header]])
    ua_stub = sys.modules["uiautomation"]
    monkeypatch.setattr(ua_stub, "ControlFromHandle", lambda handle: container, raising=False)
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(
        pick_sign=PickerSign.VIRTUAL_LIST, ext_data={"handle": 1001, "item_tag": "ListItemControl"}
    )
    result = _run(handler._handle_virtual_list(req))
    payload = json.loads(result["data"])
    assert [node["name"] for node in payload] == ["A"]


def test_ws_VIRTUAL_LIST缺句柄报错():
    handler = PickerRequestHandler(_FakeSvc())
    req = PickerRequire(pick_sign=PickerSign.VIRTUAL_LIST, ext_data={})
    result = _run(handler._handle_virtual_list(req))
    assert result["success"] is False
