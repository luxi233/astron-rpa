"""P1-2 win端冒烟: get_all_attributes / get_all_text / batch_scrape / scroll_into_view"""

import os
import sys
import types
import importlib.machinery as importlib_machinery


class _StubFinder:
    STUB_PREFIXES = (
        "win32",
        "pythoncom",
        "_winapi",
        "pywintypes",
        "uiautomation",
        "pyautogui",
        "mouseinfo",
        "tkinter",
        "psutil",
    )
    STUB_EXACT = (
        "astronverse.locator",
        "astronverse.locator.locator",
        "astronverse.software",
        "astronverse.software.software",
        "astronverse.software.core_unix",
        "astronverse.software.core_win",
    )

    def _should_stub(self, name):
        return name in self.STUB_EXACT or name.split(".")[0].startswith(self.STUB_PREFIXES)

    def find_spec(self, name, path=None, target=None):
        if self._should_stub(name):
            spec = importlib_machinery.ModuleSpec(name, self)
            return spec
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)

        def _getattr(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return lambda *a, **kw: None

        mod.__getattr__ = _getattr
        return mod

    def exec_module(self, module):
        module.__path__ = []


sys.meta_path.insert(0, _StubFinder())
_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(_here, "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(_here, "..", "..", "..", "astronverse-winelement", "src")))

import astronverse.winelement.winele as winele_mod  # noqa: E402
from astronverse.winelement.winele import WinEleExtension  # noqa: E402

# PickerDomain 被 stub, 打补丁恢复 UIA 值判断
winele_mod.PickerDomain = types.SimpleNamespace(UIA=types.SimpleNamespace(value="UIA"))


class FakeRect:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b


class FakeControl:
    def __init__(self, name="", children=None, class_name="Btn", scrollable=False, parent=None):
        self.Name = name
        self.ClassName = class_name
        self.ControlTypeName = "ButtonControl"
        self.LocalizedControlType = "按钮"
        self.AutomationId = "btn-1"
        self.ProcessId = 1234
        self.FrameworkId = "Win32"
        self.IsEnabled = True
        self.IsKeyboardFocusable = False
        self.HasKeyboardFocus = False
        self.IsPassword = False
        self.HelpText = ""
        self.AriaRole = ""
        self.AriaProperties = ""
        self.Culture = 0
        self.NativeWindowHandle = 0
        self.BoundingRectangle = FakeRect(10, 20, 110, 60)
        self._children = children or []
        self._scrollable = scrollable
        self._parent = parent
        self.scroll_calls = 0

    def IsOffscreen(self):
        return False

    def GetChildren(self):
        return list(self._children)

    def GetValuePattern(self):
        raise RuntimeError("no value pattern")

    def GetLegacyIAccessiblePattern(self):
        raise RuntimeError("no legacy pattern")

    def GetScrollItemPattern(self):
        if self._scrollable:
            self.scroll_calls += 1
            return types.SimpleNamespace(ScrollIntoView=lambda: None)
        raise RuntimeError("no scroll item pattern")

    def GetParentControl(self):
        return self._parent


class FakeLocator:
    def __init__(self, control):
        self._c = control
        self.moved = False

    def control(self):
        return self._c

    def point(self):
        return types.SimpleNamespace(x=60, y=40)

    def move(self, p):
        self.moved = True


FIND_RESULT = [None]  # 可变槽位: None=找不到, control=单个, ("list", [controls])=相似列表


def fake_find(pick=None, wait_time=0):
    res = FIND_RESULT[0]
    if res is None:
        raise RuntimeError("element not found")
    if isinstance(res, tuple) and res[0] == "list":
        return [FakeLocator(c) for c in res[1]]
    return FakeLocator(res)


winele_mod.WinEleCore.find = staticmethod(fake_find)


def mk_pick(name="x"):
    return {"elementData": {"path": [{"marker": name}], "type": "UIA"}}


# 1. get_all_attributes
btn = FakeControl(name="确定", class_name="Button")
FIND_RESULT[0] = btn
attrs, cnt = WinEleExtension.get_all_attributes(pick=mk_pick())
assert attrs["Name"] == "确定", attrs
assert attrs["ClassName"] == "Button", attrs
assert attrs["ControlTypeName"] == "ButtonControl", attrs
assert attrs["BoundingRectangle"] == "(10,20,110,60)", attrs
assert "Value" not in attrs
assert cnt == len(attrs)

# 2. get_all_text 递归收集
child1 = FakeControl(name="姓名")
child2 = FakeControl(name="年龄", children=[FakeControl(name="(岁)")])
container = FakeControl(name="表单", children=[child1, child2])
FIND_RESULT[0] = container
joined, tlist, tcnt = WinEleExtension.get_all_text(pick=mk_pick())
assert "表单" in tlist and "姓名" in tlist and "年龄" in tlist and "(岁)" in tlist, tlist
assert tcnt == len(tlist) == 4
assert joined.count("\n") == 3, repr(joined)

# 3. get_all_text include_self=False
joined2, tlist2, _ = WinEleExtension.get_all_text(pick=mk_pick(), include_self=False)
assert "表单" not in tlist2 and "姓名" in tlist2, tlist2
assert set(tlist2) == {"姓名", "年龄", "(岁)"}, tlist2

# 4. batch_scrape: 2行数据
row1 = FakeControl(name="行1", children=[FakeControl(name="张三"), FakeControl(name="25")])
row2 = FakeControl(name="行2", children=[FakeControl(name="李四"), FakeControl(name="30")])
FIND_RESULT[0] = ("list", [row1, row2])
rows, rcnt = WinEleExtension.batch_scrape(pick=mk_pick())
assert rows == [["张三", "25"], ["李四", "30"]], rows
assert rcnt == 2

# 5. batch_scrape: 元素找不到(find抛异常) → 异常传播
FIND_RESULT[0] = None
try:
    WinEleExtension.batch_scrape(pick=mk_pick())
    raise SystemExit("FAIL: 应抛异常")
except Exception as e:
    assert "element not found" in str(e), str(e)

# 6. scroll_into_view: 元素自身可滚动
target = FakeControl(name="目标", scrollable=True)
FIND_RESULT[0] = target
WinEleExtension.scroll_into_view(pick=mk_pick())
assert target.scroll_calls == 1

# 7. scroll_into_view: 父级可滚动
parent_scroll = FakeControl(name="容器", scrollable=True)
target2 = FakeControl(name="目标", parent=parent_scroll)
FIND_RESULT[0] = target2
WinEleExtension.scroll_into_view(pick=mk_pick())
assert parent_scroll.scroll_calls == 1

# 8. scroll_into_view: 均不可滚动报错
target3 = FakeControl(name="目标")
FIND_RESULT[0] = target3
try:
    WinEleExtension.scroll_into_view(pick=mk_pick())
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "不支持滚动" in e.message, e.message

# 9. scroll_into_view + auto_click 路径不炸(pyautogui已stub)
target4 = FakeControl(name="目标", scrollable=True)
FIND_RESULT[0] = target4
WinEleExtension.scroll_into_view(pick=mk_pick(), auto_click=True)
assert target4.scroll_calls == 1

print("SMOKE P1-2(win) 9/9 PASS")
