"""browser组件断言冒烟(macOS需stub平台模块)"""

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

from astronverse.browser import browser_assert  # noqa: E402
from astronverse.browser.browser_element import BrowserElement  # noqa: E402

BrowserElement.wait_element = staticmethod(lambda **kw: True)


class _FakeBrowser:
    pass


fake_browser = _FakeBrowser()
browser_assert.Assert.assert_element(
    browser_obj=fake_browser, element_data={"elementData": {"path": [], "app": "chrome"}}, wait_time=1
)
BrowserElement.wait_element = staticmethod(lambda **kw: False)
try:
    browser_assert.Assert.assert_element(
        browser_obj=fake_browser,
        element_data={"elementData": {"path": [], "app": "chrome"}},
        wait_time=1,
        error_message="登录按钮未出现",
    )
    print("FAIL: 应抛异常")
except BaseException as e:
    assert "登录按钮未出现" in str(e), str(e)
print("SMOKE ASSERT(browser) ALL PASS")
