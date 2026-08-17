"""M9 P3-1 Web增强18原子冒烟：FakeBrowser + node执行runJS代码(fake DOM) + 参数/错误分支"""

import base64
import io
import json
import subprocess
import sys
import tempfile

# ---- stub macOS 不可用的 Windows/定位模块(与 meta 生成一致) ----
import importlib.machinery as _machinery
import types as _types


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
        mod = _types.ModuleType(spec.name)

        def _getattr(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return _Stub(f"{spec.name}.{attr}")

        mod.__getattr__ = _getattr
        return mod

    def exec_module(self, module):
        module.__path__ = []


sys.meta_path.insert(0, _StubFinder())
fake_core = _types.ModuleType("astronverse.software.core_unix")


class _FakeSW:
    def __getattr__(self, n):
        raise NotImplementedError(n)


fake_core.SoftwareCore = _FakeSW
sys.modules["astronverse.software.core_unix"] = fake_core

import platform as _platform  # noqa: E402

_platform.system = lambda: "Linux"

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-browser/src")

from astronverse.browser.browser_element import BrowserElement  # noqa: E402
from astronverse.browser.browser_software import BrowserSoftware  # noqa: E402
from astronverse.browser import (  # noqa: E402
    BorderStyleType,
    CommonForBrowserType,
    CommonJsLibType,
    JsImportType,
)

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


# ---------------- node runJS 执行器 ----------------
NODE_PRELUDE = r"""
// ---- mini fake DOM ----
var __els = {};
var __storage = {session: {}, local: {}};
var __computed = {};
var __scripts = [];
var __removed = [];
var __rects = {};
var __clicked = [];
var __opts = [];
var onExpand = null;
function mkEl(xp, texts) {
  var el = {
    _xp: xp, innerText: (texts||[]).join(''), _texts: texts||[],
    style: {}, removed: false,
    remove: function(){ this.removed = true; __removed.push(this._xp); },
    getBoundingClientRect: function(){ return (__rects[this._xp]||{top:0,left:0,width:0,height:0}); },
    click: function(){ __clicked.push(this._xp); if(onExpand){ onExpand(); } }
  };
  __els[xp] = el;
  return el;
}
var sessionStorage = {
  get length(){ return Object.keys(__storage.session).length; },
  key: function(i){ return Object.keys(__storage.session)[i]; },
  getItem: function(k){ return __storage.session[k]; }
};
var localStorage = {
  get length(){ return Object.keys(__storage.local).length; },
  key: function(i){ return Object.keys(__storage.local)[i]; },
  getItem: function(k){ return __storage.local[k]; }
};
function getComputedStyle(el){ return __computed[el._xp] || {}; }
var document = {
  documentElement: {style:{}}, body: {style:{}},
  head: { appendChild: function(s){ __scripts.push(s); } },
  createElement: function(){ return {type:'', src:'', textContent:''}; },
  querySelector: function(sel){
    if (sel === 'meta[name=viewport]') return { setAttribute: function(k,v){ __viewport = v; } };
    return null;
  },
  querySelectorAll: function(sel){ return __opts; },
  evaluate: function(xp, ctx, _, type) {
    var el = __els[xp];
    if (type === 9) { return { get singleNodeValue(){ return el || null; } }; }
    var list = el ? [el] : [];
    return { get snapshotLength(){ return list.length; }, snapshotItem: function(i){ return list[i]; } };
  },
  createTreeWalker: function(el) {
    var texts = el._texts.slice(); var idx = 0;
    return { nextNode: function(){ return idx < texts.length ? {textContent: texts[idx++]} : null; } };
  }
};
var NodeFilter = { SHOW_TEXT: 4 };
var XPathResult = { ANY_TYPE: 0, FIRST_ORDERED_NODE_TYPE: 9, ORDERED_NODE_SNAPSHOT_TYPE: 7 };
var __viewport = '';
var __scrollLog = [];
var __closed = false;
var window = {
  innerWidth: 800, innerHeight: 600, scrollX: 0, scrollY: 0,
  scrollTo: function(x, y){ this.scrollY = y; __scrollLog.push(y); },
  close: function(){ __closed = true; }
};
"""


def run_js(code, env_js=""):
    """在 node mini-DOM 中执行原子生成的 JS, 返回 main() 结果"""
    full = (
        NODE_PRELUDE
        + "\n"
        + env_js
        + "\n(async function(){"
        + code
        + "\n})().then(function(r){ process.stdout.write(JSON.stringify(r===undefined?null:r)); })"
        + ".catch(function(e){ process.stdout.write(JSON.stringify({__error__: String(e && e.message || e)})); });\n"
    )
    proc = subprocess.run(["node", "-e", full], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return {"__error__": proc.stderr[-300:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"__error__": "bad json: " + proc.stdout[:200]}


class FakeBrowser:
    """拦截 send_browser_extension: runJS→node, 其他 key→预置响应"""

    def __init__(self, env_js="", responses=None):
        self.browser_type = CommonForBrowserType.BTChrome
        self._env = env_js
        self._responses = responses or {}
        self.calls = []

    def get_url(self):
        return self._responses.get("__url", "http://keep.example.com/")

    def send_browser_extension(self, browser_type, key, data=None, timeout=None):
        self.calls.append((key, data))
        if key == "runJS":
            return run_js(data["code"], self._env)
        if key in self._responses:
            resp = self._responses[key]
            if isinstance(resp, Exception):
                raise resp
            return resp
        return None


def expect_raise(name, fn, **kwargs):
    try:
        fn(**kwargs)
        check(name, False, "未抛出异常")
    except BaseException as e:
        keywords = (
            "XPath不能为空",
            "URL不能为空",
            "脚本内容不能为空",
            "浏览器对象为空",
            "未找到可用浏览器",
            "选项文本不能为空",
            "不支持的JS库",
            "触发元素XPath不能为空",
            "参数异常",
        )
        all_text = str(e) + " " + " ".join(str(a) for a in getattr(e, "args", []))
        check(name, any(w in all_text for w in keywords), repr(e))


print("== BrowserSoftware 8 atoms ==")
# 1. get_session_storage
b = FakeBrowser(env_js="__storage.session={'token':'abc','uid':'42'};")
r = BrowserSoftware.get_session_storage(browser_obj=b)
check("get_session_storage", r == {"token": "abc", "uid": "42"}, repr(r))

# 2. get_local_storage
b = FakeBrowser(env_js="__storage.local={'theme':'dark'};")
r = BrowserSoftware.get_local_storage(browser_obj=b)
check("get_local_storage", r == {"theme": "dark"}, repr(r))

# 3. cancel_html_zoom
b = FakeBrowser(env_js="document.documentElement.style.zoom='1.5'; document.body.style.transform='scale(2)';")
r = BrowserSoftware.cancel_html_zoom(browser_obj=b)
check("cancel_html_zoom", r is True, repr(r))

# 4. close_other_tabs
b = FakeBrowser(
    responses={
        "getAllTabs": [
            {"url": "http://keep.example.com/"},
            {"url": "http://a.com/"},
            {"url": "http://b.com/"},
            "not_a_dict",
        ],
    }
)
r = BrowserSoftware.close_other_tabs(browser_obj=b)
check("close_other_tabs", r == 2 and sum(1 for k, _ in b.calls if k == "closeTab") == 2, repr(r))

# 5. force_close_web
b = FakeBrowser(responses={"closeTab": True})
check("force_close_web_ext", BrowserSoftware.force_close_web(browser_obj=b, url="http://x.com/") is True)
b2 = FakeBrowser(responses={"closeTab": RuntimeError("blocked")})
check("force_close_web_fallback", BrowserSoftware.force_close_web(browser_obj=b2, url="http://x.com/") is True)

# 6. get_browser_type (注: browser_obj=None 分支因 atomic wrapper 过滤 None kwarg 在 direct call 不可达, 生产环境编辑器恒传对象)
check("get_browser_type", BrowserSoftware.get_browser_type(browser_obj=FakeBrowser()) == "chrome")

# 7. import_js_library url/text
b = FakeBrowser()
r = BrowserSoftware.import_js_library(browser_obj=b, import_type=JsImportType.Url, url="https://cdn.example.com/l.js")
check("import_js_url", r is True and len(b.calls) == 1, repr(r))
b = FakeBrowser()
r = BrowserSoftware.import_js_library(browser_obj=b, import_type=JsImportType.Text, js_content="console.log(1)")
check("import_js_text", r is True, repr(r))
expect_raise(
    "import_js_url_empty",
    BrowserSoftware.import_js_library,
    browser_obj=FakeBrowser(),
    import_type=JsImportType.Url,
    url="",
)
expect_raise(
    "import_js_text_empty",
    BrowserSoftware.import_js_library,
    browser_obj=FakeBrowser(),
    import_type=JsImportType.Text,
    js_content="",
)

# 8. import_common_js_library
b = FakeBrowser()
r = BrowserSoftware.import_common_js_library(browser_obj=b, lib_name=CommonJsLibType.Lodash)
check("import_common_lib", r is True, repr(r))
b = FakeBrowser()
r = BrowserSoftware.import_common_js_library(browser_obj=b, lib_name=CommonJsLibType.Html2Canvas)
check("import_common_lib_h2c", r is True, repr(r))
expect_raise(
    "import_common_lib_bad",
    BrowserSoftware.import_common_js_library,
    browser_obj=FakeBrowser(),
    lib_name=BorderStyleType.Solid,
)  # 非法库值(借其他枚举触发不支持分支)

print("== BrowserElement 10 atoms ==")
XP = "//div[@class='t']"

# 9. get_text_nodes
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)}, ['hello', ' ', 'world']);")
r = BrowserElement.get_text_nodes(browser_obj=b, xpath=XP)
check("get_text_nodes", r == ["hello", "world"], repr(r))
expect_raise("get_text_nodes_empty_xpath", BrowserElement.get_text_nodes, browser_obj=FakeBrowser(), xpath="")

# 10. universal_set_select (异步选项出现)
env = (
    f"mkEl({json.dumps(XP)}); "
    "onExpand = function(){ setTimeout(function(){ "
    "__opts = [mkEl('//li[1]', ['OptionA']), mkEl('//li[2]', ['OptionB'])]; }, 100); };"
)
b = FakeBrowser(env_js=env)
r = BrowserElement.universal_set_select(browser_obj=b, xpath=XP, option_text="OptionB", wait_timeout=1)
check("universal_set_select_hit", r is True, repr(r))
b = FakeBrowser(env_js=env)
r = BrowserElement.universal_set_select(browser_obj=b, xpath=XP, option_text="NotExist", wait_timeout=1)
check("universal_set_select_timeout", r is False, repr(r))
expect_raise(
    "universal_set_select_empty",
    BrowserElement.universal_set_select,
    browser_obj=FakeBrowser(),
    xpath="",
    option_text="x",
)

# 11-13. 颜色三件套
env_color = (
    f"mkEl({json.dumps(XP)}); "
    f"__computed[{json.dumps(XP)}]={{color:'rgb(255, 0, 0)', backgroundColor:'rgb(0, 128, 0)',"
    " backgroundImage:'url(\\\"https://img.example.com/a.png\\\")'};"
)
b = FakeBrowser(env_js=env_color)
check("get_font_color", BrowserElement.get_font_color(browser_obj=b, xpath=XP) == "rgb(255, 0, 0)")
b = FakeBrowser(env_js=env_color)
check("get_background_color", BrowserElement.get_background_color(browser_obj=b, xpath=XP) == "rgb(0, 128, 0)")
b = FakeBrowser(env_js=env_color)
check(
    "get_background_image",
    BrowserElement.get_background_image(browser_obj=b, xpath=XP) == "https://img.example.com/a.png",
)
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)}); __computed[{json.dumps(XP)}]={{backgroundImage:'none'}};")
check("get_background_image_none", BrowserElement.get_background_image(browser_obj=b, xpath=XP) == "")
try:
    BrowserElement.get_font_color(browser_obj=FakeBrowser(), xpath="//missing")
    check("get_font_color_missing", False, "未抛出")
except BaseException:
    check("get_font_color_missing", True)

# 14. element_add_border
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)});")
r = BrowserElement.element_add_border(
    browser_obj=b, xpath=XP, border_width=3, border_style=BorderStyleType.Dashed, border_color="blue"
)
check("element_add_border", r is True, repr(r))

# 15-17. show/hide/remove
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)});")
check("element_show", BrowserElement.element_show(browser_obj=b, xpath=XP) is True)
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)});")
check("element_hide", BrowserElement.element_hide(browser_obj=b, xpath=XP) is True)
b = FakeBrowser(env_js=f"mkEl({json.dumps(XP)});")
check("element_remove", BrowserElement.element_remove(browser_obj=b, xpath=XP) is True)
expect_raise("element_hide_empty_xpath", BrowserElement.element_hide, browser_obj=FakeBrowser(), xpath="")

# 18. element_long_screenshot (captureScreen 返回 PIL 生成的固定截图)
from PIL import Image  # noqa: E402

shot = Image.new("RGB", (800, 600), (200, 30, 30))
buf = io.BytesIO()
shot.save(buf, "PNG")
shot_b64 = base64.b64encode(buf.getvalue()).decode()

elem_top, elem_h, elem_left, elem_w = 100.0, 1500.0, 50.0, 700.0
env = (
    f"mkEl({json.dumps(XP)}); "
    f"__rects[{json.dumps(XP)}]={{top:0,left:0,width:0,height:0}};"
    f"var __r=__rects[{json.dumps(XP)}];"
    f"__r.top={elem_top}; __r.left={elem_left}; __r.width={elem_w}; __r.height={elem_h};"
)
b = FakeBrowser(env_js=env, responses={"captureScreen": shot_b64})
with tempfile.TemporaryDirectory() as td:
    path = BrowserElement.element_long_screenshot(browser_obj=b, xpath=XP, image_path=td, image_name="long.png")
    img = Image.open(path)
    # step = 600*0.8 = 480 → 段高480×3+尾段60 = 1500 (无重叠拼接)
    check("long_screenshot_size", img.size == (int(elem_w), int(elem_h)), f"size={img.size}")
    # 滚动恢复: 最后一次调用应为 runJS(restore scrollTo 0)
    check(
        "long_screenshot_restore",
        b.calls[-1][0] == "runJS" and b.calls[-1][1]["code"].find("scrollTo") >= 0,
        str(b.calls[-1]),
    )

print(f"\nTOTAL: {PASS} PASS, {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
