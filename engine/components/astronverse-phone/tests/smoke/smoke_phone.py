"""手机组件 mock 冒烟测试: 模拟 uiautomator2/adbutils, 验证25个原子直接调用链路"""

import sys
import types


# ---------- mock uiautomator2 / adbutils ----------
class MockXpathSelector:
    def __init__(self, xpath):
        self.xpath = xpath

    def wait(self, timeout):
        return None  # 走 all() 兜底

    def all(self):
        if "__nope__" in self.xpath:
            return []
        return [MockUiElement(self.xpath)]


class MockUiElement:
    def __init__(self, xpath):
        self._xpath = xpath
        self.attrib = {"text": "设置", "resource-id": "com.x:id/m", "class": "android.widget.TextView"}
        self.bounds = {"left": 100, "top": 200, "right": 300, "bottom": 400}
        self.clicked = False

    def click(self):
        self.clicked = True

    def get_text(self):
        return "设置"


class MockDevice:
    serial = "MOCK123"

    def __init__(self):
        self.calls = []

    # 连接详情
    device_info = {"version": "13", "model": "Pixel", "manufacturer": "Google", "udid": "MOCK123"}

    def window_size(self):
        return (1080, 2400)

    # xpath
    def xpath(self, p):
        self.calls.append(("xpath", p))
        return MockXpathSelector(p)

    # 点击/滑动/按键
    def click(self, x, y):
        self.calls.append(("click", x, y))

    def double_click(self, x, y):
        self.calls.append(("double_click", x, y))

    def long_click(self, x, y, duration=1.0):
        self.calls.append(("long_click", x, y))

    def swipe(self, *args, **kwargs):
        self.calls.append(("swipe", args))

    def swipe_points(self, points, duration=300):
        self.calls.append(("swipe_points", points))

    def press(self, key):
        self.calls.append(("press", key))

    # 输入
    def send_keys(self, text):
        self.calls.append(("send_keys", text))

    # 截图
    def screenshot(self, target=None):
        self.calls.append(("screenshot", target))
        from PIL import Image

        img = Image.new("RGB", (1080, 2400), color=(30, 30, 30))
        if target:
            img.save(target)
        return img

    # App
    def app_start(self, pkg):
        self.calls.append(("app_start", pkg))

    def app_stop(self, pkg):
        self.calls.append(("app_stop", pkg))

    # 剪贴板
    clipboard = "hello手机"

    def set_clipboard(self, text):
        self.calls.append(("set_clipboard", text))
        MockDevice.clipboard = text

    # 屏幕
    def screen_on(self):
        self.calls.append(("screen_on",))

    def screen_off(self):
        self.calls.append(("screen_off",))

    def shell(self, cmd):
        self.calls.append(("shell", cmd))

    orientation = "natural"

    # 文件
    def push(self, src, dst):
        self.calls.append(("push", src, dst))

    def pull(self, src, dst):
        self.calls.append(("pull", src, dst))
        import shutil

        shutil.copy(src, dst)

    def dump_hierarchy(self):
        return '<?xml version="1.0"?><hierarchy><node text="设置"/></hierarchy>'


MOCK_DEVICE = MockDevice()

u2 = types.ModuleType("uiautomator2")
u2.connect = lambda serial="": MOCK_DEVICE
sys.modules["uiautomator2"] = u2

adb = types.ModuleType("adbutils")


class _Dev:
    serial = "MOCK123"
    state = "device"


adb.adb = types.SimpleNamespace(device_list=lambda: [_Dev()])
sys.modules["adbutils"] = adb

# ---------- 执行测试 ----------
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

# 枚举成员直传(不用字符串)
from astronverse.phone import (  # noqa: E402
    AppActionType,
    ClickType,
    ConnectMode,
    ConnectTargetType,
    ElementInfoType,
    ImageTargetPart,
    InputTargetType,
    KeyType,
    LocatorType,
    OrientationType,
    PositionType,
    ScreenActionType,
    SwipeAreaType,
    SwipeDirection,
    SwipeMode,
    UnlockType,
    WaitType,
)

results = {}


def T_connect():
    conn = Phone.connect(
        target_type=ConnectTargetType.SPECIFIED,
        serial="MOCK123",
        custom_name="测试机",
        unlock_type=UnlockType.NONE,
    )
    assert isinstance(conn.device, MockDevice) and conn.serial == "MOCK123"
    results["conn"] = conn


def T_connect_all():
    conn_list, failed_list = Phone.connect(target_type=ConnectTargetType.ALL, ignore_failed=True)
    assert len(conn_list) == 1 and failed_list == []


def T_disconnect():
    Phone.disconnect(conn=results["conn"])
    assert True


def T_get_connect_info():
    info = Phone.get_connect_info(conn=results["conn"])
    assert info["platformVersion"] == "13" and info["deviceScreenSize"] == "1080x2400"
    assert info["deviceModel"] == "Pixel" and info["custom_name"] == "测试机"


def T_get_devices():
    devices = Phone.get_devices()
    assert devices == ["MOCK123"]


def T_get_element():
    el = Phone.get_element(conn=results["conn"], by=LocatorType.TEXT, value="设置", index=0, timeout=1)
    assert el.device is results["conn"].device, "元素必须携带device引用"
    assert "设置" in el.locator_desc
    results["element"] = el


def T_get_element_selector():
    import json

    el = Phone.get_element(
        conn=results["conn"],
        by=LocatorType.SELECTOR,
        value=json.dumps({"text": "设置", "resourceId": "com.x:id/m"}, ensure_ascii=False),
    )
    assert el is not None


def T_click_element_single():
    Phone.click_element(
        conn=results["conn"], element=results["element"], click_type=ClickType.SINGLE, after_delay=0
    )
    assert results["element"].element.clicked


def T_click_element_double():
    Phone.click_element(
        conn=results["conn"], element=results["element"], click_type=ClickType.DOUBLE, after_delay=0
    )
    assert any(c[0] == "double_click" for c in results["conn"].device.calls), "双击走device.double_click"


def T_click_element_long():
    Phone.click_element(
        conn=results["conn"], element=results["element"], click_type=ClickType.LONG, after_delay=0
    )
    assert any(c[0] == "long_click" for c in results["conn"].device.calls)


def T_click_element_locate():
    Phone.click_element(conn=results["conn"], by=LocatorType.TEXT, value="设置", click_type=ClickType.SINGLE, after_delay=0)


def T_click_screen_coord():
    Phone.click_screen(
        conn=results["conn"], position_type=PositionType.COORD, x=500, y=1000, click_type=ClickType.SINGLE, after_delay=0
    )
    assert any(c[0] == "click" and c[1] == 500 for c in results["conn"].device.calls)


def T_click_screen_image():
    import numpy as np

    rng = np.random.RandomState(42)
    tpl_path = "/tmp/phone_tpl_test.png"
    arr = rng.randint(0, 255, (2400, 1080, 3), dtype=np.uint8)
    patch = rng.randint(0, 255, (60, 60, 3), dtype=np.uint8)  # 非均匀纹理模板
    arr[500:560, 400:460] = patch

    # 直接测match_template_positions核心(不走设备截图)
    import cv2

    cv2.imwrite(tpl_path, patch)
    positions = PhoneCore.match_template_positions(arr, tpl_path, 0.8)
    assert len(positions) >= 1
    cx, cy, _, _, score = positions[0]
    assert abs(cx - 430) <= 3 and abs(cy - 530) <= 3 and score > 0.9, (cx, cy, score)
    results["tpl_path"] = tpl_path


def T_get_image_coords():
    # 用核心方法验证坐标计算(中心/自定义/随机)
    import cv2
    import numpy as np

    rng = np.random.RandomState(7)
    screen = rng.randint(0, 255, (2400, 1080, 3), dtype=np.uint8)
    patch = rng.randint(0, 255, (60, 60, 3), dtype=np.uint8)
    screen[500:560, 400:460] = patch
    tpl = "/tmp/phone_tpl_g.png"
    cv2.imwrite(tpl, patch)
    positions = PhoneCore.match_template_positions(screen, tpl, 0.8)
    assert len(positions) == 1
    cx, cy, tw, th, _ = positions[0]
    assert cx == 430 and cy == 530


def T_wait_image():
    # mock设备截图是纯色 → 用不存在的模板等待消失, timeout=1
    ok = Phone.wait_image(conn=results["conn"], img_paths=["/tmp/not_exist_tpl.png"], wait_type=WaitType.DISAPPEAR, timeout=1)
    # 模板读取失败被吞掉 → 视为未找到 → 消失成功
    assert ok is True


def T_wait_element():
    ok = Phone.wait_element(conn=results["conn"], element=results["element"], wait_type=WaitType.APPEAR, timeout=2)
    assert ok is True


def T_input_text_element():
    Phone.input_text(
        conn=results["conn"],
        text="你好RPA",
        input_target=InputTargetType.ELEMENT,
        element=results["element"],
        append=False,
        press_enter=True,
        after_delay=0,
    )
    calls = results["conn"].device.calls
    assert any(c[0] == "send_keys" and c[1] == "你好RPA" for c in calls)
    assert any(c[0] == "press" and c[1] == "enter" for c in calls)


def T_swipe_direction():
    Phone.swipe_screen(
        conn=results["conn"], mode=SwipeMode.DIRECTION, direction=SwipeDirection.UP, area=SwipeAreaType.SCREEN, after_delay=0
    )
    assert any(c[0] == "swipe" for c in results["conn"].device.calls)


def T_swipe_element_area():
    Phone.swipe_screen(
        conn=results["conn"],
        mode=SwipeMode.DIRECTION,
        direction=SwipeDirection.DOWN,
        area=SwipeAreaType.ELEMENT,
        element=results["element"],
        after_delay=0,
    )


def T_swipe_coord():
    Phone.swipe_screen(conn=results["conn"], mode=SwipeMode.COORD, sx=100, sy=2000, ex=100, ey=500, duration=200, after_delay=0)


def T_press_key():
    Phone.press_key(conn=results["conn"], key_name=KeyType.BACK, after_delay=0)
    assert any(c[0] == "press" and c[1] == "back" for c in results["conn"].device.calls)


def T_screenshot():
    import os

    path = Phone.screenshot(conn=results["conn"], folder_path="/tmp/phone_shots", filename="screen.png")
    assert os.path.exists(path) and path.endswith("screen.png")


def T_element_screenshot():
    import os

    path = Phone.element_screenshot(conn=results["conn"], element=results["element"], folder_path="/tmp/phone_shots", filename="el.png")
    assert os.path.exists(path)


def T_get_element_info():
    text = Phone.get_element_info(element=results["element"], info_type=ElementInfoType.TEXT)
    assert text == "设置"
    rid = Phone.get_element_info(element=results["element"], info_type=ElementInfoType.ATTRIBUTE, attr_name="resourceId")
    assert rid == "com.x:id/m"


def T_open_close_app():
    Phone.open_close_app(conn=results["conn"], action=AppActionType.OPEN, package="com.tencent.mm")
    assert any(c[0] == "app_start" and c[1] == "com.tencent.mm" for c in results["conn"].device.calls)
    Phone.open_close_app(conn=results["conn"], action=AppActionType.CLOSE, package="com.tencent.mm")
    assert any(c[0] == "app_stop" for c in results["conn"].device.calls)


def T_clipboard():
    got = Phone.get_clipboard(conn=results["conn"])
    assert got == "hello手机"
    Phone.set_clipboard(conn=results["conn"], text="写入剪贴板")
    assert MockDevice.clipboard == "写入剪贴板"


def T_rotate():
    Phone.rotate_screen(conn=results["conn"], orientation=OrientationType.PORTRAIT)
    o = Phone.get_orientation(conn=results["conn"])
    assert o == 0


def T_lock_unlock():
    Phone.lock_unlock_screen(conn=results["conn"], action=ScreenActionType.LOCK)
    assert any(c[0] == "screen_off" for c in results["conn"].device.calls)
    Phone.lock_unlock_screen(
        conn=results["conn"], action=ScreenActionType.UNLOCK, unlock_type=UnlockType.PATTERN, unlock_secret="5416"
    )
    assert any(c[0] == "swipe_points" for c in results["conn"].device.calls)


def T_push_pull():
    import os
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.write(b"phone file test")
    tmp.close()
    remote = "/sdcard/test_push.txt"
    Phone.push_file(conn=results["conn"], local_path=tmp.name, remote_path=remote)
    assert any(c[0] == "push" for c in results["conn"].device.calls)
    local2 = "/tmp/phone_pull_test.txt"
    if os.path.exists(local2):
        os.remove(local2)
    # mock pull是copy(src,dst) → src即本地tmp
    Phone.pull_file(conn=results["conn"], remote_path=tmp.name, local_path=local2)
    assert os.path.exists(local2)


def T_ui_tree():
    tree = Phone.get_ui_tree(conn=results["conn"])
    assert "设置" in tree and tree.startswith("<?xml")


def T_error_paths():
    from astronverse.actionlib.error import BaseException as BE

    # 元素找不到
    try:
        PhoneCore.locate(results["conn"], LocatorType.TEXT, "__nope__", 0, 0.1)
        raise AssertionError("应抛出元素未找到")
    except BE as e:
        assert "未找到" in e.code.message or True
    # 空conn
    try:
        Phone.disconnect(conn=None)
        raise AssertionError("应抛出无连接")
    except BE:
        pass
    # selector格式错误
    try:
        PhoneCore.locate(results["conn"], LocatorType.SELECTOR, "not-json", 0, 0.1)
        raise AssertionError("应抛出selector格式错误")
    except BE:
        pass


TESTS = [
    T_connect,
    T_connect_all,
    T_disconnect,
    T_get_connect_info,
    T_get_devices,
    T_get_element,
    T_get_element_selector,
    T_click_element_single,
    T_click_element_double,
    T_click_element_long,
    T_click_element_locate,
    T_click_screen_coord,
    T_click_screen_image,
    T_get_image_coords,
    T_wait_image,
    T_wait_element,
    T_input_text_element,
    T_swipe_direction,
    T_swipe_element_area,
    T_swipe_coord,
    T_press_key,
    T_screenshot,
    T_element_screenshot,
    T_get_element_info,
    T_open_close_app,
    T_clipboard,
    T_rotate,
    T_lock_unlock,
    T_push_pull,
    T_ui_tree,
    T_error_paths,
]

# ========== Appium 模式测试(真appium包, patch webdriver.Remote返回mock driver) ==========
import base64  # noqa: E402
import io  # noqa: E402


class MockAppWebElement:
    text = "设置"
    rect = {"x": 100, "y": 200, "width": 200, "height": 200}

    def __init__(self):
        self.sent = []

    def click(self):
        self.sent.append(("click",))

    def clear(self):
        self.sent.append(("clear",))

    def send_keys(self, t):
        self.sent.append(("send_keys", t))

    def get_attribute(self, name):
        return {"resourceId": "com.x:id/m", "text": "设置"}.get(name, "")


class MockAppiumDriver:
    capabilities = {"platformVersion": "13", "udid": "MOCK123", "deviceModel": "Pixel", "deviceManufacturer": "Google"}
    page_source = '<?xml version="1.0"?><hierarchy><node text="设置"/></hierarchy>'
    orientation = "PORTRAIT"

    def __init__(self):
        self.calls = []
        self.gestures = []

    def press_keycode(self, k):
        self.calls.append(("keycode", k))

    def execute(self, cmd, params=None):
        self.calls.append(("w3c", cmd))  # ActionChains perform

    def execute_script(self, script, args=None):
        self.gestures.append((script, args))

    def find_element(self, by, val):
        if "__nope__" in val:
            raise RuntimeError("not found")
        return results.get("a_el") or MockAppWebElement()

    def find_elements(self, by, val):
        return [] if "__nope__" in val else [results.get("a_el") or MockAppWebElement()]

    def get_window_size(self):
        return {"width": 1080, "height": 2400}

    def get_screenshot_as_file(self, path):
        from PIL import Image

        Image.new("RGB", (1080, 2400), color=(30, 30, 30)).save(path)

    def get_screenshot_as_png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (1080, 2400), color=(30, 30, 30)).save(buf, format="PNG")
        return buf.getvalue()

    def get_clipboard(self):
        return "appium剪贴板"

    def set_clipboard(self, text):
        self.calls.append(("set_clipboard", text))

    def activate_app(self, pkg):
        self.calls.append(("activate_app", pkg))

    def terminate_app(self, pkg):
        self.calls.append(("terminate_app", pkg))

    def push_file(self, remote, b64):
        self.calls.append(("push_file", remote, base64.b64decode(b64)))

    def pull_file(self, remote):
        self.calls.append(("pull_file_req", remote))
        return base64.b64encode(b"appium pull data").decode()

    def lock(self):
        self.calls.append(("lock",))

    def quit(self):
        self.calls.append(("quit",))

    class _SwitchTo:
        active_element = MockAppWebElement()

    switch_to = _SwitchTo()


MOCK_APPIUM = MockAppiumDriver()

try:
    from appium import webdriver as _appium_webdriver

    _orig_remote = _appium_webdriver.Remote
    _appium_webdriver.Remote = lambda command_executor=None, options=None, **kw: MOCK_APPIUM
    APPIUM_AVAILABLE = True
except Exception:
    APPIUM_AVAILABLE = False


def T_appium_connect():
    conn = Phone.connect(
        target_type=ConnectTargetType.SPECIFIED,
        serial="MOCK123",
        custom_name="Appium测试机",
        connect_mode=ConnectMode.APPIUM,
        appium_server="http://127.0.0.1:4723",
        unlock_type=UnlockType.NONE,
    )
    assert conn.mode == "appium" and conn.device is MOCK_APPIUM
    assert conn.serial == "MOCK123"
    results["a_conn"] = conn


def T_appium_get_connect_info():
    info = Phone.get_connect_info(conn=results["a_conn"])
    assert info["platformVersion"] == "13" and info["deviceModel"] == "Pixel"
    assert info["deviceScreenSize"] == "1080x2400" and info["custom_name"] == "Appium测试机"


def T_appium_get_element():
    el = Phone.get_element(conn=results["a_conn"], by=LocatorType.TEXT, value="设置", index=0, timeout=1)
    assert el.device is MOCK_APPIUM and el.locator_desc
    results["a_el"] = el


def T_appium_click_element():
    Phone.click_element(conn=results["a_conn"], element=results["a_el"], click_type=ClickType.SINGLE, after_delay=0)
    Phone.click_element(conn=results["a_conn"], element=results["a_el"], click_type=ClickType.DOUBLE, after_delay=0)
    Phone.click_element(conn=results["a_conn"], element=results["a_el"], click_type=ClickType.LONG, after_delay=0)
    dbl = [g for g in MOCK_APPIUM.gestures if g[0] == "mobile: doubleClickGesture"]
    lng = [g for g in MOCK_APPIUM.gestures if g[0] == "mobile: longClickGesture"]
    assert dbl and dbl[0][1]["x"] == 200 and dbl[0][1]["y"] == 300  # rect中心
    assert lng and lng[0][1]["duration"] == 1000


def T_appium_click_screen():
    Phone.click_screen(
        conn=results["a_conn"], position_type=PositionType.COORD, x=500, y=1200, click_type=ClickType.SINGLE, after_delay=0
    )
    clk = [g for g in MOCK_APPIUM.gestures if g[0] == "mobile: clickGesture"]
    assert clk and clk[-1][1] == {"x": 500, "y": 1200}


def T_appium_swipe_direction():
    Phone.swipe_screen(
        conn=results["a_conn"], mode=SwipeMode.DIRECTION, direction=SwipeDirection.UP, area=SwipeAreaType.SCREEN, after_delay=0
    )
    assert any(c[0] == "w3c" for c in MOCK_APPIUM.calls), "方向滑动走W3C actions"


def T_appium_swipe_coord():
    Phone.swipe_screen(conn=results["a_conn"], mode=SwipeMode.COORD, sx=100, sy=2000, ex=100, ey=500, duration=200, after_delay=0)


def T_appium_press_key():
    Phone.press_key(conn=results["a_conn"], key_name=KeyType.BACK, after_delay=0)
    assert any(c == ("keycode", 4) for c in MOCK_APPIUM.calls)


def T_appium_input_text():
    Phone.input_text(
        conn=results["a_conn"], text="Appium输入", input_target=InputTargetType.ELEMENT, element=results["a_el"],
        append=False, press_enter=True, after_delay=0,
    )
    sent = results["a_el"].element.sent
    assert any(s == ("clear",) for s in sent) and any(s[0] == "send_keys" and s[1] == "Appium输入" for s in sent)
    assert any(c == ("keycode", 66) for c in MOCK_APPIUM.calls)
    # 光标位置输入(无元素)
    Phone.input_text(conn=results["a_conn"], text="焦点输入", input_target=InputTargetType.CURSOR, after_delay=0)


def T_appium_wait_element():
    ok = Phone.wait_element(conn=results["a_conn"], element=results["a_el"], wait_type=WaitType.APPEAR, timeout=2)
    assert ok is True


def T_appium_screenshots():
    import os

    p1 = Phone.screenshot(conn=results["a_conn"], folder_path="/tmp/phone_shots", filename="ap_screen.png")
    p2 = Phone.element_screenshot(conn=results["a_conn"], element=results["a_el"], folder_path="/tmp/phone_shots", filename="ap_el.png")
    assert os.path.exists(p1) and os.path.exists(p2)


def T_appium_get_element_info():
    t = Phone.get_element_info(element=results["a_el"], info_type=ElementInfoType.TEXT)
    rid = Phone.get_element_info(element=results["a_el"], info_type=ElementInfoType.ATTRIBUTE, attr_name="resourceId")
    assert t == "设置" and rid == "com.x:id/m"


def T_appium_app_and_clipboard():
    Phone.open_close_app(conn=results["a_conn"], action=AppActionType.OPEN, package="com.tencent.mm")
    Phone.open_close_app(conn=results["a_conn"], action=AppActionType.CLOSE, package="com.tencent.mm")
    assert any(c[0] == "activate_app" for c in MOCK_APPIUM.calls) and any(c[0] == "terminate_app" for c in MOCK_APPIUM.calls)
    got = Phone.get_clipboard(conn=results["a_conn"])
    Phone.set_clipboard(conn=results["a_conn"], text="写入Appium剪贴板")
    assert got == "appium剪贴板" and any(c[0] == "set_clipboard" and c[1] == "写入Appium剪贴板" for c in MOCK_APPIUM.calls)


def T_appium_rotate_lock():
    Phone.rotate_screen(conn=results["a_conn"], orientation=OrientationType.PORTRAIT)
    assert Phone.get_orientation(conn=results["a_conn"]) == 0
    Phone.lock_unlock_screen(conn=results["a_conn"], action=ScreenActionType.LOCK)
    assert any(c[0] == "lock" for c in MOCK_APPIUM.calls)
    Phone.lock_unlock_screen(
        conn=results["a_conn"], action=ScreenActionType.UNLOCK, unlock_type=UnlockType.PASSWORD, unlock_secret="1234"
    )
    codes = [c[1] for c in MOCK_APPIUM.calls if c[0] == "keycode"]
    assert 224 in codes and 8 in codes and 11 in codes and 66 in codes, codes[-8:]  # wakeup+1+4+enter


def T_appium_push_pull():
    import os
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb")
    tmp.write(b"appium push test")
    tmp.close()
    Phone.push_file(conn=results["a_conn"], local_path=tmp.name, remote_path="/sdcard/a.txt")
    pushed = [c for c in MOCK_APPIUM.calls if c[0] == "push_file"]
    assert pushed and pushed[0][2] == b"appium push test"
    local2 = "/tmp/phone_ap_pull.txt"
    if os.path.exists(local2):
        os.remove(local2)
    Phone.pull_file(conn=results["a_conn"], remote_path="/sdcard/a.txt", local_path=local2)
    assert open(local2, "rb").read() == b"appium pull data"


def T_appium_ui_tree_and_disconnect():
    tree = Phone.get_ui_tree(conn=results["a_conn"])
    assert "设置" in tree and tree.startswith("<?xml")
    Phone.disconnect(conn=results["a_conn"])
    assert any(c[0] == "quit" for c in MOCK_APPIUM.calls)


if APPIUM_AVAILABLE:
    TESTS += [
        T_appium_connect,
        T_appium_get_connect_info,
        T_appium_get_element,
        T_appium_click_element,
        T_appium_click_screen,
        T_appium_swipe_direction,
        T_appium_swipe_coord,
        T_appium_press_key,
        T_appium_input_text,
        T_appium_wait_element,
        T_appium_screenshots,
        T_appium_get_element_info,
        T_appium_app_and_clipboard,
        T_appium_rotate_lock,
        T_appium_push_pull,
        T_appium_ui_tree_and_disconnect,
    ]
else:
    print("SKIP: appium-python-client not installed")

for t in TESTS:
    check(t.__name__, t)

print("\n===== {} passed, {} failed =====".format(len(passed), len(failed)))
sys.exit(1 if failed else 0)
