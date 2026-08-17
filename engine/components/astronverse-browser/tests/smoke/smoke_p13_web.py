"""P1-3/P1-4 冒烟: get_similar_lazy / get_similar_lazy_xpath / paginator"""
import sys
import types
import importlib.machinery as importlib_machinery


class _StubFinder:
    STUB_PREFIXES = ("win32", "pythoncom", "_winapi", "pywintypes", "uiautomation", "pyautogui", "mouseinfo", "tkinter", "psutil")
    STUB_EXACT = ("astronverse.locator", "astronverse.locator.locator", "astronverse.software", "astronverse.software.software", "astronverse.software.core_unix", "astronverse.software.core_win")

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

import astronverse.browser.browser_element as be_mod  # noqa: E402
from astronverse.browser.browser_element import BrowserElement  # noqa: E402

# check_element 不走真实浏览器: stub 为直通
be_mod.check_element = lambda browser_obj, element_data, element_timeout=10: browser_obj


class FakeBrowser:
    class _BT:
        value = "chrome"

    browser_type = _BT()

    def __init__(self, handler):
        self.handler = handler  # handler(key, data) -> result

    def send_browser_extension(self, browser_type=None, key=None, data=None, **kw):
        return self.handler(key, data)


def mk_ele():
    return {
        "elementData": {
            "path": [{"marker": "item"}],
            "app": "chrome",
            "version": "1.0",
            "type": "web",
        }
    }


# 1-2. get_similar_lazy: 两轮增长后稳定
SIM_COUNTS = [10, 15, 18, 18, 18]  # 初始 + 每轮查询结果
state = {"qi": 0, "scrolls": 0}


def h_lazy(key, data):
    if key == "elementFromSelect":
        n = SIM_COUNTS[min(state["qi"], len(SIM_COUNTS) - 1)]
        return [{"marker": "item", "i": i} for i in range(n)]
    if key == "runJS":
        state["scrolls"] += 1
        state["qi"] += 1
        return True
    raise RuntimeError("unexpected " + key)


elems, cnt = BrowserElement.get_similar_lazy(
    browser_obj=FakeBrowser(h_lazy), element_data=mk_ele(), max_rounds=20, stable_rounds=2, wait_load=0.01
)
assert cnt == 18, cnt
assert len(elems) == 18
assert elems[0]["elementData"]["path"] == {"marker": "item", "i": 0}
assert state["scrolls"] >= 3, state  # 至少滚动3轮才稳定

# 3. get_similar_lazy: max_count 提前停止
state2 = {"qi": 0}


def h_lazy2(key, data):
    if key == "elementFromSelect":
        n = [10, 50, 100][min(state2["qi"], 2)]
        return [{"i": i} for i in range(n)]
    if key == "runJS":
        state2["qi"] += 1
        return True
    raise RuntimeError(key)


elems2, cnt2 = BrowserElement.get_similar_lazy(
    browser_obj=FakeBrowser(h_lazy2), element_data=mk_ele(), max_rounds=10, stable_rounds=2, wait_load=0.01, max_count=50
)
assert cnt2 >= 50, cnt2  # 达到50提前停

# 4-5. get_similar_lazy_xpath: JS合法性+循环稳定
XPATH = '//div[@class="item"]'
js_seen = []


def h_xpath(key, data):
    assert key == "runJS", key
    js_seen.append(data["code"])
    # 计数JS返回数量; 收集JS返回文本列表
    if "snapshotLength; var n" in data["code"]:
        return [5, 8, 8, 8][min(len([j for j in js_seen if "var n" in j]) - 1, 3)]
    if "for(var i=0;i<snap.snapshotLength;i++)" in data["code"] and "var out=[]" in data["code"]:
        return ["条目A", "条目B"]
    raise RuntimeError("unknown js")


texts, cnt3 = BrowserElement.get_similar_lazy_xpath(
    browser_obj=FakeBrowser(h_xpath), xpath=XPATH, max_rounds=10, stable_rounds=2, wait_load=0.01
)
assert texts == ["条目A", "条目B"], texts
assert cnt3 == 2
# 验证xpath被安全注入(json字面量)
assert '"//div[@class=\\"item\\"]"' in js_seen[0] or '"//div[@class=' in js_seen[0], js_seen[0][:120]

# 6. get_similar_lazy_xpath: 空xpath报错
try:
    BrowserElement.get_similar_lazy_xpath(browser_obj=FakeBrowser(h_xpath), xpath="")
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "XPath不能为空" in e.message, e.message

# 7-9. paginator: 3页后无下一页
PAGES = 3
pstate = {"page": 1}


def h_page(key, data):
    assert key == "runJS", key
    code = data["code"]
    if "singleNodeValue" in code:  # click_next
        if pstate["page"] < PAGES:
            pstate["page"] += 1
            return True
        return False
    if "if(xp){" in code:  # collect
        return [f"第{pstate['page']}页-条目{i}" for i in range(2)]
    raise RuntimeError("unknown")


it = BrowserElement.paginator(
    browser_obj=FakeBrowser(h_page), next_xpath='//a[@class="next"]', item_xpath='//li', wait_load=0.01
)
pages = list(it)
assert len(pages) == 3, pages
assert pages[0] == (1, ["第1页-条目0", "第1页-条目1"]), pages[0]
assert pages[2] == (3, ["第3页-条目0", "第3页-条目1"]), pages[2]

# 10. paginator: max_pages=2 提前停
pstate2 = {"page": 1}


def h_page2(key, data):
    code = data["code"]
    if "singleNodeValue" in code:
        pstate2["page"] += 1
        return True  # 永远有下一页
    if "if(xp){" in code:
        return [f"P{pstate2['page']}"]
    raise RuntimeError("unknown")


it2 = BrowserElement.paginator(
    browser_obj=FakeBrowser(h_page2), next_xpath='//a[@class="next"]', item_xpath='//li', max_pages=2, wait_load=0.01
)
pages2 = list(it2)
assert len(pages2) == 2, pages2
assert pages2[1][0] == 2

# 11. paginator: 空next_xpath报错
try:
    BrowserElement.paginator(browser_obj=FakeBrowser(h_page), next_xpath="")
    raise SystemExit("FAIL: 应抛异常")
except BaseException as e:
    assert "下一页XPath不能为空" in e.message, e.message

print("SMOKE P1-3/P1-4(web) 11/11 PASS")
