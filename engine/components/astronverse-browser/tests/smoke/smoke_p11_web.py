"""P1-1 web端冒烟: wait_any_element / wait_any_group / combine_elements"""

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
sys.path.insert(0, "src")

from astronverse.browser.browser_element import BrowserElement  # noqa: E402


def mk_ele(name):
    """构造 WebPick, path 里带元素名供 mock 识别"""
    return {"elementData": {"path": [{"marker": name}], "app": "chrome"}}


class FakeBrowser:
    class _BT:
        value = "chrome"

    browser_type = _BT()

    def __init__(self, ready_markers):
        self.ready_markers = set(ready_markers)

    def send_browser_extension(self, browser_type=None, key=None, data=None, **kw):
        if key == "elementIsReady":
            markers = [d.get("marker") for d in data if isinstance(d, dict)]
            return bool(markers) and all(m in self.ready_markers for m in markers)
        raise RuntimeError("unexpected key " + str(key))


# 1. wait_any_element: 第2个元素命中
b = FakeBrowser(["ele_b"])
name, ok = BrowserElement.wait_any_element(
    browser_obj=b, element_1=mk_ele("ele_a"), element_2=mk_ele("ele_b"), element_timeout=2
)
assert (name, ok) == ("元素2", True), (name, ok)

# 2. wait_any_element: 自定义名称
name, ok = BrowserElement.wait_any_element(
    browser_obj=b,
    element_1=mk_ele("ele_a"),
    name_1="登录页",
    element_2=mk_ele("ele_b"),
    name_2="首页",
    element_timeout=2,
)
assert (name, ok) == ("首页", True), (name, ok)

# 3. wait_any_element: 全部超时
b_none = FakeBrowser([])
name, ok = BrowserElement.wait_any_element(
    browser_obj=b_none, element_1=mk_ele("ele_a"), element_2=mk_ele("ele_b"), element_timeout=1
)
assert (name, ok) == ("", False), (name, ok)

# 4. wait_any_element: 无元素报错
try:
    BrowserElement.wait_any_element(browser_obj=b, element_timeout=1)
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要拾取一个元素" in e.message, e.message

# 5. wait_any_group: 组B全出现命中
b2 = FakeBrowser(["b1", "b2"])
gname, ok = BrowserElement.wait_any_group(
    browser_obj=b2,
    group_a_name="登录页",
    element_a_1=mk_ele("a1"),
    group_b_name="列表页",
    element_b_1=mk_ele("b1"),
    element_b_2=mk_ele("b2"),
    element_timeout=2,
)
assert (gname, ok) == ("列表页", True), (gname, ok)

# 6. wait_any_group: 组内只出现部分, 超时不命中
b3 = FakeBrowser(["b1"])
gname, ok = BrowserElement.wait_any_group(
    browser_obj=b3,
    element_a_1=mk_ele("a1"),
    element_b_1=mk_ele("b1"),
    element_b_2=mk_ele("b2"),
    element_timeout=1,
)
assert (gname, ok) == ("", False), (gname, ok)

# 7. wait_any_group: 无组报错
try:
    BrowserElement.wait_any_group(browser_obj=b, element_timeout=1)
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要配置一组元素" in e.message, e.message

# 8. combine_elements
e1, e2 = mk_ele("x"), mk_ele("y")
elems, count = BrowserElement.combine_elements(element_1=e1, element_2=e2)
assert elems == [e1, e2] and count == 2, (elems, count)

# 9. combine_elements: 全空报错
try:
    BrowserElement.combine_elements()
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "至少需要拾取一个元素" in e.message, e.message

print("SMOKE P1-1(web) 9/9 PASS")
