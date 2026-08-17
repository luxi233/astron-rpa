"""M7 手机组件冒烟: 15新原子 + ClickType DOWN/UP, mock u2/appium 双模式"""

import base64
import io
import sys
import tempfile
import types

import numpy as np


# ---------- mock uiautomator2 / adbutils ----------
class Touch:
    def __init__(self, calls):
        self._calls = calls

    def down(self, x, y):
        self._calls.append(("touch.down", x, y))

    def up(self, x, y):
        self._calls.append(("touch.up", x, y))


class MockUiElement:
    def __init__(self, xpath):
        self._xpath = xpath
        self.attrib = {"text": "设置", "resource-id": "com.x:id/m", "class": "android.widget.TextView"}
        self.bounds = {"left": 100, "top": 200, "right": 300, "bottom": 400}

    def click(self):
        pass

    def get_text(self):
        return "设置"


# 合成长页面: 行唯一纹理 (i*7+j*3)%256, 灰度图
LONG_H, VIEW_W, VIEW_H, STEP = 1000, 120, 200, 150
long_rows = ((np.arange(LONG_H)[:, None] * 7 + np.arange(VIEW_W)[None, :] * 3) % 256).astype(np.uint8)
LONG_IMG = np.stack([long_rows] * 3, axis=-1)  # H,W,3


class MockDevice:
    serial = "MOCK123"
    device_info = {"version": "13", "model": "Pixel", "manufacturer": "Google", "udid": "MOCK123"}
    clipboard = ""
    orientation = "natural"

    def __init__(self):
        self.calls = []
        self.swipe_count = 0
        self.scroll_pos = 0
        self.touch = Touch(self.calls)

    def window_size(self):
        return (VIEW_W, VIEW_H)

    def xpath(self, p):
        self.calls.append(("xpath", p))
        return MockSelector(p, self)

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def double_click(self, x, y):
        self.calls.append(("double_click", x, y))

    def long_click(self, x, y, duration=1.0):
        self.calls.append(("long_click", x, y))

    def swipe(self, *args, **kwargs):
        self.calls.append(("swipe", args))
        self.swipe_count += 1
        self.scroll_pos = min(self.scroll_pos + STEP, LONG_H - VIEW_H)  # 向上滑=内容下移

    def press(self, key):
        self.calls.append(("press", key))

    def send_keys(self, text):
        self.calls.append(("send_keys", text))

    def screenshot(self, target=None):
        from PIL import Image

        img = Image.fromarray(LONG_IMG[self.scroll_pos : self.scroll_pos + VIEW_H])
        if target:
            img.save(target)
        return img

    def app_start(self, pkg):
        self.calls.append(("app_start", pkg))

    def app_stop(self, pkg):
        self.calls.append(("app_stop", pkg))

    def app_install(self, path):
        self.calls.append(("app_install", path))

    def set_clipboard(self, text):
        self.calls.append(("set_clipboard", text))

    def shell(self, cmd):
        self.calls.append(("shell", cmd))
        return shell_answer(cmd)

    def push(self, src, dst):
        self.calls.append(("push", src, dst))

    def pull(self, src, dst):
        self.calls.append(("pull", src, dst))

    def dump_hierarchy(self):
        return '<?xml version="1.0"?><hierarchy><node text="设置"/></hierarchy>'


class MockSelector:
    def __init__(self, xpath, device):
        self.xpath = xpath
        self.device = device

    def wait(self, timeout):
        return None

    def all(self):
        if "__nope__" in self.xpath:
            return []
        if "lazy" in self.xpath:
            return [MockUiElement(self.xpath)] if self.device.swipe_count >= 2 else []
        return [MockUiElement(self.xpath)]


LS_OUTPUT = "a.txt\nb.png\nCam/\nDCIM/\nzz.doc\n"


def shell_answer(cmd):
    if cmd.startswith("ls -1p"):
        return LS_OUTPUT
    if "[ -f" in cmd:
        return "1"
    if "[ -d" in cmd:
        return "0"
    return ""


MOCK_DEVICE = MockDevice()

u2 = types.ModuleType("uiautomator2")
u2.connect = lambda serial="": MOCK_DEVICE
sys.modules["uiautomator2"] = u2


class MockAdbDevice:
    def __init__(self, serial=""):
        self.serial = serial

    def shell(self, cmd):
        return "ADB-OK: {}".format(cmd)

    def install(self, path):
        return "install {}".format(path)


adb = types.ModuleType("adbutils")


class _Dev:
    serial = "MOCK123"
    state = "device"


adb.adb = types.SimpleNamespace(
    device_list=lambda: [_Dev()],
    device=lambda serial="": MockAdbDevice(serial),
)
sys.modules["adbutils"] = adb

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-phone/src")

passed, failed = [], []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print("PASS:", name)
    except Exception as e:
        failed.append((name, repr(e)))
        print("FAIL:", name, "->", repr(e))


from astronverse.phone.phone import Phone  # noqa: E402
from astronverse.phone.phone_core import PhoneCore  # noqa: E402
from astronverse.phone import ClickType, ConnectMode, ConnectTargetType, ListSortType, LocatorType, PositionType, SwipeDirection, UnlockType  # noqa: E402

results = {}
from astronverse.actionlib.error import BaseException as BE  # noqa: E402


# ---------- u2 模式 ----------
def T_connect():
    conn = Phone.connect(
        target_type=ConnectTargetType.SPECIFIED,
        serial="MOCK123",
        unlock_type=UnlockType.NONE,
    )
    assert conn.device is MOCK_DEVICE
    results["conn"] = conn


def T_run_adb_command():
    out = Phone.run_adb_command(command="dumpsys battery", udid="")
    assert out == "ADB-OK: dumpsys battery", out


def T_click_down_up():
    Phone.click_screen(conn=results["conn"], position_type=PositionType.COORD, x=300, y=600, click_type=ClickType.DOWN, after_delay=0)
    Phone.click_screen(conn=results["conn"], position_type=PositionType.COORD, x=300, y=600, click_type=ClickType.UP, after_delay=0)
    calls = results["conn"].device.calls
    assert any(c[0] == "touch.down" and c[1] == 300 and c[2] == 600 for c in calls)
    assert any(c[0] == "touch.up" and c[1] == 300 and c[2] == 600 for c in calls)


def T_lazy_load_xpath():
    MOCK_DEVICE.swipe_count = 0
    el = Phone.lazy_load_xpath(conn=results["conn"], xpath='//*[@text="lazy-item"]', max_swipes=5, after_delay=0)
    assert el is not None and 2 <= MOCK_DEVICE.swipe_count <= 3
    assert any(c[0] == "swipe" for c in MOCK_DEVICE.calls)


def T_lazy_load_by():
    MOCK_DEVICE.swipe_count = 0
    el = Phone.lazy_load(conn=results["conn"], by=LocatorType.TEXT, value="lazy-item", max_swipes=5, after_delay=0)
    assert el is not None
    assert "lazy-item" in el.locator_desc


def T_lazy_load_not_found():
    MOCK_DEVICE.swipe_count = 0
    try:
        Phone.lazy_load_xpath(conn=results["conn"], xpath='//*[@text="__nope__"]', max_swipes=2, after_delay=0)
        raise AssertionError("应抛未找到")
    except BE:
        pass


def T_scroll_screenshot():
    MOCK_DEVICE.scroll_pos = 0
    path = Phone.scroll_screenshot(conn=results["conn"], folder_path="/tmp/phone_m7", filename="long.png", max_scrolls=0, after_delay=0)
    from PIL import Image

    got = np.asarray(Image.open(path).convert("RGB"))
    assert got.shape == (LONG_H, VIEW_W, 3), got.shape
    assert np.array_equal(got, LONG_IMG), "拼接结果必须与原始长图逐像素一致"


def T_scroll_screenshot_max_limit():
    MOCK_DEVICE.scroll_pos = 0
    Phone.scroll_screenshot(conn=results["conn"], folder_path="/tmp/phone_m7", filename="long2.png", max_scrolls=2, after_delay=0)
    assert True


def T_install_apk():
    tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
    tmp.write(b"PK-fake")
    tmp.close()
    Phone.install_apk(conn=results["conn"], apk_path=tmp.name)
    assert any(c[0] == "app_install" and c[1] == tmp.name for c in MOCK_DEVICE.calls)


def T_install_apk_missing():
    try:
        Phone.install_apk(conn=results["conn"], apk_path="/tmp/__no_such__.apk")
        raise AssertionError("应抛APK不存在")
    except BE:
        pass


def T_file_ops():
    conn = results["conn"]
    Phone.delete_file(conn=conn, path="/sdcard/a.txt")
    Phone.delete_folder(conn=conn, path="/sdcard/old")
    Phone.create_folder(conn=conn, path="/sdcard/new/dir")
    Phone.rename_file(conn=conn, old_path="/sdcard/a.txt", new_path="/sdcard/b.txt")
    Phone.rename_folder(conn=conn, old_path="/sdcard/x", new_path="/sdcard/y")
    cmds = [c[1] for c in MOCK_DEVICE.calls if c[0] == "shell"]
    assert 'rm -f "/sdcard/a.txt"' in cmds
    assert 'rm -rf "/sdcard/old"' in cmds
    assert 'mkdir -p "/sdcard/new/dir"' in cmds
    assert 'mv "/sdcard/a.txt" "/sdcard/b.txt"' in cmds
    assert 'mv "/sdcard/x" "/sdcard/y"' in cmds


def T_exists():
    conn = results["conn"]
    assert Phone.file_exists(conn=conn, path="/sdcard/a.txt") is True
    assert Phone.folder_exists(conn=conn, path="/sdcard/old") is False


def T_list_entries():
    conn = results["conn"]
    files = Phone.get_file_list(conn=conn, folder="/sdcard", pattern="*", sort_type=ListSortType.ASC)
    assert files == ["a.txt", "b.png", "zz.doc"], files
    files_desc = Phone.get_file_list(conn=conn, folder="/sdcard", pattern="*", sort_type=ListSortType.DESC)
    assert files_desc == ["zz.doc", "b.png", "a.txt"]
    pngs = Phone.get_file_list(conn=conn, folder="/sdcard", pattern="*.png")
    assert pngs == ["b.png"]
    folders = Phone.get_folder_list(conn=conn, folder="/sdcard", pattern="*")
    assert folders == ["Cam", "DCIM"]
    dcim = Phone.get_folder_list(conn=conn, folder="/sdcard", pattern="D*")
    assert dcim == ["DCIM"]


def T_refresh_file():
    Phone.refresh_file(conn=results["conn"], path="/sdcard/DCIM/新图.png")
    cmds = [c[1] for c in MOCK_DEVICE.calls if c[0] == "shell"]
    assert any("MEDIA_SCANNER_SCAN_FILE" in c and "file:///sdcard/DCIM/新图.png" in c for c in cmds), cmds[-3:]


def T_error_paths():
    try:
        Phone.run_adb_command(command="")
        raise AssertionError("空命令应报错")
    except BE:
        pass
    try:
        Phone.delete_file(conn=results["conn"], path="")
        raise AssertionError("空路径应报错")
    except BE:
        pass
    try:
        Phone.scroll_screenshot(conn=results["conn"], folder_path="/tmp/phone_m7", direction=SwipeDirection.LEFT, after_delay=0)
        raise AssertionError("横向应报错")
    except BE:
        pass


TESTS = [
    T_connect,
    T_run_adb_command,
    T_click_down_up,
    T_lazy_load_xpath,
    T_lazy_load_by,
    T_lazy_load_not_found,
    T_scroll_screenshot,
    T_scroll_screenshot_max_limit,
    T_install_apk,
    T_install_apk_missing,
    T_file_ops,
    T_exists,
    T_list_entries,
    T_refresh_file,
    T_error_paths,
]


# ---------- Appium 模式 ----------
class MockAppWebElement:
    text = "设置"
    rect = {"x": 100, "y": 200, "width": 200, "height": 200}

    def click(self):
        pass


class MockAppiumDriver:
    capabilities = {"platformVersion": "13", "udid": "MOCK123", "deviceModel": "Pixel", "deviceManufacturer": "Google"}
    page_source = '<?xml version="1.0"?><hierarchy/>'
    orientation = "PORTRAIT"

    def __init__(self):
        self.calls = []
        self.gestures = []
        self.w3c_count = 0

    def execute(self, cmd, params=None):
        self.w3c_count += 1
        self.calls.append(("w3c", cmd))

    def execute_script(self, script, args=None):
        self.gestures.append((script, args))
        if script == "mobile: shell":
            return shell_answer((args or {}).get("command", ""))
        return None

    def find_element(self, by, val):
        if "__nope__" in val:
            raise RuntimeError("not found")
        return MockAppWebElement()

    def find_elements(self, by, val):
        if "__nope__" in val:
            return []
        if "lazy" in val:
            return [MockAppWebElement()] if self.w3c_count >= 1 else []
        return [MockAppWebElement()]

    def get_window_size(self):
        return {"width": 1080, "height": 2400}

    def get_screenshot_as_png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (200, 200), color=(10, 20, 30)).save(buf, format="PNG")
        return buf.getvalue()

    def press_keycode(self, k):
        self.calls.append(("keycode", k))

    def activate_app(self, pkg):
        self.calls.append(("activate_app", pkg))

    def quit(self):
        self.calls.append(("quit",))

    def lock(self):
        self.calls.append(("lock",))


MOCK_APPIUM = MockAppiumDriver()

try:
    from appium import webdriver as _appium_webdriver

    _appium_webdriver.Remote = lambda command_executor=None, options=None, **kw: MOCK_APPIUM
    APPIUM_AVAILABLE = True
except Exception:
    APPIUM_AVAILABLE = False


def T_appium_connect():
    conn = Phone.connect(
        target_type=ConnectTargetType.SPECIFIED,
        serial="MOCK123",
        connect_mode=ConnectMode.APPIUM,
        unlock_type=UnlockType.NONE,
    )
    assert conn.mode == "appium"
    results["a_conn"] = conn


def T_appium_adb_shell_ops():
    conn = results["a_conn"]
    Phone.delete_file(conn=conn, path="/sdcard/x.apk")
    shells = [g for g in MOCK_APPIUM.gestures if g[0] == "mobile: shell"]
    assert shells and 'rm -f "/sdcard/x.apk"' in shells[-1][1]["command"], MOCK_APPIUM.gestures[-3:]
    assert Phone.file_exists(conn=conn, path="/sdcard/x.apk") is True
    files = Phone.get_file_list(conn=conn, folder="/sdcard", pattern="*.png")
    assert files == ["b.png"], files


def T_appium_click_down_up():
    before = MOCK_APPIUM.w3c_count
    Phone.click_screen(conn=results["a_conn"], position_type=PositionType.COORD, x=400, y=800, click_type=ClickType.DOWN, after_delay=0)
    Phone.click_screen(conn=results["a_conn"], position_type=PositionType.COORD, x=400, y=800, click_type=ClickType.UP, after_delay=0)
    assert MOCK_APPIUM.w3c_count >= before + 2, "DOWN/UP走W3C actions"


def T_appium_lazy_load():
    MOCK_APPIUM.w3c_count = 0
    el = Phone.lazy_load_xpath(conn=results["a_conn"], xpath='//*[@text="lazy-item"]', max_swipes=3, after_delay=0)
    assert el is not None


def T_appium_install_apk():
    tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
    tmp.write(b"PK-appium")
    tmp.close()
    Phone.install_apk(conn=results["a_conn"], apk_path=tmp.name)
    assert any(g[0] == "mobile: installApp" and g[1]["appPath"] == tmp.name for g in MOCK_APPIUM.gestures)


if APPIUM_AVAILABLE:
    TESTS += [
        T_appium_connect,
        T_appium_adb_shell_ops,
        T_appium_click_down_up,
        T_appium_lazy_load,
        T_appium_install_apk,
    ]
else:
    print("SKIP: appium-python-client not installed")

for t in TESTS:
    check(t.__name__, t)

print("\n===== {} passed, {} failed =====".format(len(passed), len(failed)))
sys.exit(1 if failed else 0)
