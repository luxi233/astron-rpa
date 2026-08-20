"""M10 P3-2 IFrame跨域9原子冒烟：FakeBrowser + node多文档fake DOM(模拟插件frame路由) + 参数/错误分支"""

import json
import subprocess
import sys
import types

# ---- stub macOS 不可用的 Windows/定位模块(与 meta 生成一致) ----
import importlib.machinery as _machinery


class _Stub:
    def __init__(self, name):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Stub(f"{self._name}.{attr}")

    def __call__(self, *a, **k):
        raise NotImplementedError(f"stubbed: {self._name}")


class _StubFinder:
    PREFIXES = (
        "win32",
        "pythoncom",
        "_winapi",
        "pywintypes",
        "uiautomation",
        "pyautogui",
        "mouseinfo",
        "tkinter",
        "clipboard",
    )
    EXACT = ("astronverse.locator", "astronverse.locator.locator")

    def _should_stub(self, name):
        return name in self.EXACT or name.split(".")[0].startswith(self.PREFIXES)

    def find_spec(self, name, path=None, target=None):
        if self._should_stub(name):
            spec = _machinery.ModuleSpec(name, self)
            return spec
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)

        def _getattr(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return _Stub(f"{spec.name}.{attr}")

        mod.__getattr__ = _getattr
        return mod

    def exec_module(self, module):
        module.__path__ = []


sys.meta_path.insert(0, _StubFinder())
fake_core = types.ModuleType("astronverse.software.core_unix")


class _FakeSW:
    def __getattr__(self, n):
        raise NotImplementedError(n)


fake_core.SoftwareCore = _FakeSW
sys.modules["astronverse.software.core_unix"] = fake_core

import platform as _platform  # noqa: E402

_platform.system = lambda: "Linux"

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-browser/src"))

from astronverse.browser.browser import Browser  # noqa: E402
from astronverse.browser.browser_iframe import BrowserIframe  # noqa: E402
from astronverse.browser import FrameLocateType, FrameWaitStatusTypeFlag  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


class FakeBrowser:
    """模拟 Browser：send_browser_extension 走 node 多文档 DOM，按 isFrame/iframeXpath 路由"""

    browser_type = types.SimpleNamespace(value="chrome")

    def __init__(self):
        self.frame = None
        self.last_data = None
        self.last_probe = None

    def send_browser_extension(self, browser_type=None, key=None, data=None, data_path="", timeout=None):
        assert key == "runJS", f"unexpected key {key}"
        self.last_data = data
        payload = dict(data)
        if getattr(self, "_pre", None):
            payload["pre"] = self._pre
        if getattr(self, "_probe", None):
            payload["probe"] = self._probe
        out = subprocess.run(
            ["node", "/tmp/smoke_web_m10_dom.js"],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode != 0:
            raise RuntimeError(f"node error: {out.stderr[:300]}")
        res = json.loads(out.stdout.strip().splitlines()[-1])
        if not res.get("ok"):
            raise RuntimeError(res.get("err", "unknown"))
        self.last_probe = res.get("probe")
        return res.get("value")


def raises(fn, exc=BaseException):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


b = FakeBrowser()

# ---- 1. init_iframe 三种定位 ----
f = BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Index, index=0)
check("init_iframe index0 iframeXpath", f.get("iframeXpath") == "/html[1]/body[1]/iframe[1]", str(f))
check("init_iframe index0 meta", f.get("isFrame") is True and f.get("name") == "frameA" and f.get("id") == "f1", str(f))
check("init_iframe index0 src", f.get("src") == "https://a.example.com/", str(f))
check("init_iframe index0 size", f.get("width") == 100 and f.get("height") == 20, str(f))

f2 = BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Index, index=1)
check("init_iframe index1 iframeXpath", f2.get("iframeXpath") == "/html[1]/body[1]/iframe[2]", str(f2))
check("init_iframe index1 name", f2.get("name") == "frameB", str(f2))

f3 = BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Name, name="frameB")
check("init_iframe by name", f3.get("iframeXpath") == "/html[1]/body[1]/iframe[2]", str(f3))

f4 = BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Xpath, xpath='//iframe[@id="f1"]')
check("init_iframe by xpath", f4.get("iframeXpath") == "/html[1]/body[1]/iframe[1]", str(f4))

check(
    "init_iframe not found raises",
    raises(
        lambda: BrowserIframe.init_iframe(
            browser_obj=b, locate_mode=FrameLocateType.Xpath, xpath='//iframe[@id="nope"]'
        )
    ),
)
check(
    "init_iframe name empty raises",
    raises(lambda: BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Name, name="")),
)
check(
    "init_iframe xpath empty raises",
    raises(lambda: BrowserIframe.init_iframe(browser_obj=b, locate_mode=FrameLocateType.Xpath, xpath="")),
)

# ---- 2. 嵌套 init_iframe ----
fn = BrowserIframe.init_iframe(
    browser_obj=b, locate_mode=FrameLocateType.Xpath, xpath='//iframe[@name="inner"]', parent_frame=f
)
check(
    "nested iframeXpath join",
    fn.get("iframeXpath") == "/html[1]/body[1]/iframe[1]/$iframe$/html[1]/body[1]/iframe[1]",
    str(fn),
)

# ---- 3. switch_iframe ----
cur = BrowserIframe.switch_iframe(browser_obj=b)
check("switch to main", cur.get("isFrame") is False and b.frame is None, str(cur))
cur = BrowserIframe.switch_iframe(browser_obj=b, frame=f)
check("switch sets browser.frame", b.frame is f and cur.get("iframeXpath") == "/html[1]/body[1]/iframe[1]", str(cur))
check("switch invalid frame raises", raises(lambda: BrowserIframe.switch_iframe(browser_obj=b, frame={"foo": 1})))

# ---- 4. 跨 frame 路由 + 元素操作 ----
t = BrowserIframe.iframe_get_element_text(browser_obj=b, frame=f, xpath='//div[@class="msg"]')
check("get text explicit frame", t == "hello from frameA", repr(t))

t2 = BrowserIframe.iframe_get_element_text(browser_obj=b, xpath='//div[@class="msg"]')
check("get text fallback active frame", t2 == "hello from frameA", repr(t2))

t3 = BrowserIframe.iframe_get_element_text(browser_obj=b, frame=f, xpath='//div[@class="none"]')
check("get text missing -> empty", t3 == "", repr(t3))
check(
    "get text empty xpath raises",
    raises(lambda: BrowserIframe.iframe_get_element_text(browser_obj=b, frame=f, xpath="")),
)

deep = BrowserIframe.iframe_get_element_text(browser_obj=b, frame=fn, xpath='//div[@class="v"]')
check("nested frame deep text", deep == "deep text", repr(deep))

check(
    "route unknown frame -> plugin ctx error",
    raises(
        lambda: BrowserIframe.iframe_get_element_text(
            browser_obj=b, frame={"isFrame": True, "iframeXpath": "/no/such"}, xpath="//a"
        ),
        RuntimeError,
    ),
)

# ---- 5. click ----
b._probe = "function main(){ return CLICKED; } return main()"
ok = BrowserIframe.iframe_click_element(browser_obj=b, frame=f, xpath="//a")
check("click element ok", ok is True, str(ok))
check("click dispatched to element", b.last_probe == ["A"], str(b.last_probe))
b._probe = None
check(
    "click missing raises",
    raises(lambda: BrowserIframe.iframe_click_element(browser_obj=b, frame=f, xpath='//div[@class="none"]')),
)
check("click empty xpath raises", raises(lambda: BrowserIframe.iframe_click_element(browser_obj=b, frame=f, xpath="")))

# ---- 6. input ----
b._pre = None
b._probe = "function main(){ return document.evaluate('//input[@id=\"q\"]',document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue.value; } return main()"
r = BrowserIframe.iframe_input_text(
    browser_obj=b, frame=f, xpath='//input[@id="q"]', input_text="hello", overwrite=True
)
check("input overwrite ok", r is True, str(r))
check("input overwrite value", b.last_probe == "hello", repr(b.last_probe))

b._pre = 'function main(){ document.evaluate(\'//input[@id="q"]\',document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue.value="world"; } return main()'
BrowserIframe.iframe_input_text(browser_obj=b, frame=f, xpath='//input[@id="q"]', input_text="hello", overwrite=False)
check("input append value", b.last_probe == "worldhello", repr(b.last_probe))
b._pre = None
check(
    "input empty xpath raises",
    raises(lambda: BrowserIframe.iframe_input_text(browser_obj=b, frame=f, xpath="", input_text="x")),
)
check(
    "input missing element raises",
    raises(
        lambda: BrowserIframe.iframe_input_text(browser_obj=b, frame=f, xpath='//input[@id="none"]', input_text="x")
    ),
)

# ---- 7. similar list ----
lst = BrowserIframe.iframe_get_similar_list(browser_obj=b, frame=f, xpath="//ul/li")
check("similar list texts", lst == ["A", "B", "C"], str(lst))
lst2 = BrowserIframe.iframe_get_similar_list(browser_obj=b, frame=f, xpath="//a", attribute_name="href")
check("similar list attr", lst2 == ["https://a.example.com/link"], str(lst2))
check(
    "similar list empty xpath raises",
    raises(lambda: BrowserIframe.iframe_get_similar_list(browser_obj=b, frame=f, xpath="")),
)

# ---- 8. wait ----
w = BrowserIframe.iframe_wait_element(
    browser_obj=b, frame=f, xpath='//div[@class="msg"]', timeout=1, wait_status=FrameWaitStatusTypeFlag.Appear
)
check("wait appear found", w is True, str(w))
w2 = BrowserIframe.iframe_wait_element(browser_obj=b, frame=f, xpath='//div[@class="never"]', timeout=0)
check("wait appear timeout", w2 is False, str(w2))
w3 = BrowserIframe.iframe_wait_element(
    browser_obj=b, frame=f, xpath='//div[@class="msg"]', timeout=0, wait_status=FrameWaitStatusTypeFlag.Disappear
)
check("wait disappear still exists", w3 is False, str(w3))
w4 = BrowserIframe.iframe_wait_element(
    browser_obj=b, frame=f, xpath='//div[@class="never"]', timeout=1, wait_status=FrameWaitStatusTypeFlag.Disappear
)
check("wait disappear gone", w4 is True, str(w4))
check(
    "wait neg timeout raises",
    raises(lambda: BrowserIframe.iframe_wait_element(browser_obj=b, frame=f, xpath="//a", timeout=-1)),
)
check("wait empty xpath raises", raises(lambda: BrowserIframe.iframe_wait_element(browser_obj=b, frame=f, xpath="")))

# ---- 9. attribute ----
av = BrowserIframe.iframe_get_attribute(browser_obj=b, frame=f, xpath="//a", attr_name="href")
check("attr href", av == "https://a.example.com/link", repr(av))
at = BrowserIframe.iframe_get_attribute(browser_obj=b, frame=f, xpath='//div[@class="msg"]', attr_name="text")
check("attr text", at == "hello from frameA", repr(at))
am = BrowserIframe.iframe_get_attribute(browser_obj=b, frame=f, xpath="//a", attr_name="nonexistent")
check("attr missing -> empty", am == "", repr(am))
check(
    "attr empty name raises",
    raises(lambda: BrowserIframe.iframe_get_attribute(browser_obj=b, frame=f, xpath="//a", attr_name="")),
)
check(
    "attr empty xpath raises",
    raises(lambda: BrowserIframe.iframe_get_attribute(browser_obj=b, frame=f, xpath="", attr_name="href")),
)

# ---- 10. element info ----
info = BrowserIframe.iframe_get_element_info(browser_obj=b, frame=f, xpath='//input[@id="q"]')
check("info tag", info.get("tag") == "input", str(info))
check("info attrs", info.get("attributes", {}).get("id") == "q", str(info))
check("info visible", info.get("visible") is True, str(info))
check("info rect", info.get("rect", {}).get("width") == 100, str(info))
check(
    "info missing raises",
    raises(lambda: BrowserIframe.iframe_get_element_info(browser_obj=b, frame=f, xpath='//div[@class="none"]')),
)
check(
    "info empty xpath raises", raises(lambda: BrowserIframe.iframe_get_element_info(browser_obj=b, frame=f, xpath=""))
)

# ---- 11. Browser.frame 属性 ----
real = Browser()
check("Browser.frame default None", real.frame is None)

print(f"\nTOTAL: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
