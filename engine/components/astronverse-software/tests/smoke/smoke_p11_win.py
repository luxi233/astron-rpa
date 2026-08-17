"""P1-1 win端冒烟: wait_any_element / wait_any_group / combine_elements"""

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
from astronverse.winelement.winele import WinEle  # noqa: E402


def mk_pick(name):
    return {"elementData": {"path": [{"marker": name}], "type": "UIA"}}


# mock WinEleCore.find: 按全局 ready 集合决定成败
READY = set()


def fake_find(pick=None, wait_time=0):
    markers = [d.get("marker") for d in pick["elementData"]["path"] if isinstance(d, dict)]
    if markers and all(m in READY for m in markers):
        return "locator-ok"
    raise RuntimeError("element not found")


winele_mod.WinEleCore.find = staticmethod(fake_find)

# 1. wait_any_element: 第2个命中
READY.update(["ele_b"])
name, ok = WinEle.wait_any_element(pick_1=mk_pick("ele_a"), pick_2=mk_pick("ele_b"), wait_time=2)
assert (name, ok) == ("元素2", True), (name, ok)

# 2. wait_any_element: 自定义名称
name, ok = WinEle.wait_any_element(
    pick_1=mk_pick("ele_a"), name_1="主窗口", pick_2=mk_pick("ele_b"), name_2="弹窗", wait_time=2
)
assert (name, ok) == ("弹窗", True), (name, ok)

# 3. wait_any_element: 全部超时
READY.clear()
name, ok = WinEle.wait_any_element(pick_1=mk_pick("ele_a"), pick_2=mk_pick("ele_b"), wait_time=1)
assert (name, ok) == ("", False), (name, ok)

# 4. wait_any_element: 无元素报错
try:
    WinEle.wait_any_element(wait_time=1)
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要拾取一个元素" in e.message, e.message

# 5. wait_any_group: 组A全出现命中
READY.update(["a1", "a2"])
gname, ok = WinEle.wait_any_group(
    group_a_name="加载完成",
    pick_a_1=mk_pick("a1"),
    pick_a_2=mk_pick("a2"),
    group_b_name="出错页",
    pick_b_1=mk_pick("b1"),
    wait_time=2,
)
assert (gname, ok) == ("加载完成", True), (gname, ok)

# 6. wait_any_group: 部分出现超时不命中
READY.clear()
READY.update(["a1"])
gname, ok = WinEle.wait_any_group(
    pick_a_1=mk_pick("a1"),
    pick_a_2=mk_pick("a2"),
    pick_b_1=mk_pick("b1"),
    wait_time=1,
)
assert (gname, ok) == ("", False), (gname, ok)

# 7. wait_any_group: 无组报错
try:
    WinEle.wait_any_group(wait_time=1)
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要配置一组元素" in e.message, e.message

# 8. combine_elements
p1, p2 = mk_pick("x"), mk_pick("y")
picks, count = WinEle.combine_elements(pick_1=p1, pick_2=p2)
assert picks == [p1, p2] and count == 2, (picks, count)

# 9. combine_elements: 全空报错
try:
    WinEle.combine_elements()
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要拾取一个元素" in e.message, e.message

print("SMOKE P1-1(win) 9/9 PASS")
