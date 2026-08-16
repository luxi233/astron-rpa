"""手机自动化核心: 包装uiautomator2或Appium(懒加载), 所有方法为静态方法"""

from astronverse.actionlib.error import BaseException

from . import (
    AppActionType,
    ClickType,
    ConnectMode,
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
from .error import (
    PHONE_CONNECT_ERROR_FORMAT,
    PHONE_DEVICE_LIST_ERROR_FORMAT,
    PHONE_ELEMENT_ERROR_FORMAT,
    PHONE_ELEMENT_NOT_FOUND_FORMAT,
    PHONE_EXECUTE_ERROR_FORMAT,
    PHONE_FILE_ERROR_FORMAT,
    PHONE_IMAGE_ERROR_FORMAT,
    PHONE_IMAGE_NOT_FOUND_FORMAT,
)
from .phone_obj import PhoneElement, PhoneObject


def _to_enum(value, enum_cls):
    """参数可能是枚举成员或字符串, 统一转枚举"""
    if isinstance(value, enum_cls):
        return value
    for member in enum_cls:
        if member.value == value:
            return member
    return enum_cls(list(enum_cls)[0].value)


def _load_u2():
    import uiautomator2  # 懒加载: macOS/无adb环境导入不报错

    return uiautomator2


def _is_appium_device(device) -> bool:
    """duck-typing识别Appium driver(appium有press_keycode, u2只有press)"""
    return hasattr(device, "press_keycode")


def _appium_by():
    from appium.webdriver.common.appiumby import AppiumBy

    return AppiumBy


def _appium_swipe(driver, sx, sy, ex, ey, duration: int = 300):
    """Appium任意两点滑动(W3C touch actions)"""
    from selenium.webdriver.common.action_chains import ActionChains

    actions = ActionChains(driver)
    pointer = actions.w3c_actions.add_pointer_input("touch", "finger1")
    pointer.create_pointer_move(x=int(sx), y=int(sy), duration=0)
    pointer.create_pointer_down(button=0)
    pointer.create_pointer_move(x=int(ex), y=int(ey), duration=max(int(duration), 0))
    pointer.create_pointer_up(button=0)
    actions.perform()


def _window_size(device) -> tuple:
    """屏幕尺寸, 兼容u2/appium"""
    if _is_appium_device(device):
        size = device.get_window_size() or {}
        return int(size.get("width", 0)), int(size.get("height", 0))
    return device.window_size()


def _xpath_escape(value: str) -> str:
    """转义xpath属性值中的引号"""
    return str(value).replace("&", "&amp;").replace('"', "&quot;")


def _build_xpath(by: LocatorType, value: str, index: int = 0) -> str:
    """统一转换为xpath定位(支持第N个匹配)"""
    by = _to_enum(by, LocatorType)
    value = str(value)
    if by == LocatorType.ID:
        path = '//*[@resource-id="{}"]'.format(_xpath_escape(value))
    elif by == LocatorType.TEXT:
        path = '//*[@text="{}"]'.format(_xpath_escape(value))
    elif by == LocatorType.TEXT_CONTAINS:
        path = '//*[contains(@text, "{}")]'.format(_xpath_escape(value))
    elif by == LocatorType.DESCRIPTION:
        path = '//*[@content-desc="{}"]'.format(_xpath_escape(value))
    elif by == LocatorType.CLASS:
        path = '//*[@class="{}"]'.format(_xpath_escape(value))
    elif by == LocatorType.XPATH:
        path = value
    elif by == LocatorType.SELECTOR:
        # JSON字典: {"resourceId":"x","text":"y","textContains":"z"} 多条件AND
        import json

        try:
            criteria = json.loads(value) if value.strip().startswith("{") else None
        except Exception:
            criteria = None
        if not isinstance(criteria, dict) or not criteria:
            raise BaseException(
                PHONE_ELEMENT_ERROR_FORMAT.format('selector定位需要JSON字典, 如: {"text":"设置"}'),
                "selector定位格式错误",
            )
        key_map = {
            "resourceId": '@resource-id="{}"',
            "text": '@text="{}"',
            "textContains": 'contains(@text, "{}")',
            "description": '@content-desc="{}"',
            "className": '@class="{}"',
        }
        conds = []
        for k, v in criteria.items():
            if k not in key_map:
                raise BaseException(
                    PHONE_ELEMENT_ERROR_FORMAT.format("selector不支持的条件: {}".format(k)),
                    "selector条件不支持",
                )
            conds.append(key_map[k].format(_xpath_escape(v)))
        path = "//*[" + " and ".join(conds) + "]"
    else:
        path = '//*[@text="{}"]'.format(_xpath_escape(value))
    if index > 0 and not (by == LocatorType.XPATH and ("[" in path.split("/")[-1])):
        path = "{}[{}]".format(path, index + 1)
    return path


class PhoneCore:
    # ---------- 连接管理 ----------

    @staticmethod
    def list_devices() -> list:
        """列出adb已连接的设备serial列表"""
        try:
            import adbutils

            return [d.serial for d in adbutils.adb.device_list() if d.state == "device"]
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_DEVICE_LIST_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def _connect_one(serial: str = ""):
        u2 = _load_u2()
        try:
            if serial:
                return u2.connect(serial)
            return u2.connect()  # 自动选择(仅一台设备时)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(
                PHONE_CONNECT_ERROR_FORMAT.format("{} {}".format(serial, str(e))),
                str(e),
            )

    @staticmethod
    def _connect_appium(serial: str = "", server: str = "http://127.0.0.1:4723"):
        """通过Appium Server连接手机(需先启动Appium服务)"""
        try:
            from appium import webdriver
            from appium.options.android import UiAutomator2Options

            opts = UiAutomator2Options()
            opts.set_capability("platformName", "Android")
            opts.set_capability("automationName", "UiAutomator2")
            opts.set_capability("noReset", True)
            opts.set_capability("newCommandTimeout", 300)
            if serial:
                opts.set_capability("udid", serial)
            return webdriver.Remote(
                command_executor=str(server or "http://127.0.0.1:4723").rstrip("/"),
                options=opts,
            )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(
                PHONE_CONNECT_ERROR_FORMAT.format("Appium({}) {}".format(server, str(e))),
                str(e),
            )

    @classmethod
    def connect(
        cls,
        serial: str = "",
        custom_name: str = "",
        unlock_type: UnlockType = UnlockType.NONE,
        unlock_secret: str = "",
        connect_mode: ConnectMode = ConnectMode.UIAUTOMATOR2,
        appium_server: str = "http://127.0.0.1:4723",
    ) -> PhoneObject:
        """连接单台手机(指定serial或自动选择)"""
        connect_mode = _to_enum(connect_mode, ConnectMode)
        if connect_mode == ConnectMode.APPIUM:
            device = cls._connect_appium(serial, appium_server)
            if unlock_type != UnlockType.NONE:
                cls.unlock_device(device, unlock_type, unlock_secret)
            caps = getattr(device, "capabilities", None) or {}
            return PhoneObject(
                device,
                serial=serial or str(caps.get("udid", "")),
                custom_name=custom_name,
                mode="appium",
            )
        device = cls._connect_one(serial)
        if unlock_type != UnlockType.NONE:
            cls.unlock_device(device, unlock_type, unlock_secret)
        return PhoneObject(device, serial=getattr(device, "serial", serial) or serial, custom_name=custom_name)

    @classmethod
    def connect_all(
        cls,
        ignore_failed: bool = True,
        custom_name: str = "",
        unlock_type: UnlockType = UnlockType.NONE,
        unlock_secret: str = "",
        connect_mode: ConnectMode = ConnectMode.UIAUTOMATOR2,
        appium_server: str = "http://127.0.0.1:4723",
    ):
        """连接所有已连接手机, 返回(连接列表, 失败serial列表)"""
        serials = cls.list_devices()
        if not serials:
            raise BaseException(PHONE_CONNECT_ERROR_FORMAT.format("未检测到已连接的手机设备"), "no devices")
        conn_list, failed_list = [], []
        for s in serials:
            try:
                conn_list.append(cls.connect(s, custom_name, unlock_type, unlock_secret, connect_mode, appium_server))
            except Exception:
                if ignore_failed:
                    failed_list.append(s)
                else:
                    raise
        return conn_list, failed_list

    @staticmethod
    def disconnect(conn: PhoneObject):
        """断开手机连接(u2停止设备服务/appium关闭会话)"""
        try:
            device = conn.device
            if hasattr(device, "uiautomator") and hasattr(device.uiautomator, "stop"):
                device.uiautomator.stop()
            elif hasattr(device, "quit"):
                device.quit()
        except Exception:
            pass

    @staticmethod
    def get_connect_info(conn: PhoneObject) -> dict:
        """获取手机连接详情"""
        try:
            device = conn.device
            if _is_appium_device(device):
                caps = dict(getattr(device, "capabilities", None) or {})
                w, h = _window_size(device)
                return {
                    "platform": "android",
                    "platformName": "Android",
                    "platformVersion": str(caps.get("platformVersion", "")),
                    "deviceUDID": conn.serial or str(caps.get("udid", "")),
                    "deviceScreenSize": "{}x{}".format(w, h),
                    "deviceModel": str(caps.get("deviceModel", "")),
                    "deviceManufacturer": str(caps.get("deviceManufacturer", "")),
                    "custom_name": conn.custom_name or "",
                }
            info = dict(device.device_info or {})
            w, h = _window_size(device)
            return {
                "platform": "android",
                "platformName": "Android",
                "platformVersion": str(info.get("version", "")),
                "deviceUDID": conn.serial or info.get("udid", ""),
                "deviceScreenSize": "{}x{}".format(w, h),
                "deviceModel": str(info.get("model", "")),
                "deviceManufacturer": str(info.get("manufacturer", "")),
                "custom_name": conn.custom_name or "",
            }
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- 元素定位 ----------

    @classmethod
    def locate(cls, conn: PhoneObject, by: LocatorType, value: str, index: int = 0, timeout: int = 10) -> PhoneElement:
        """按定位方式获取元素对象"""
        xpath = _build_xpath(by, value, index)
        try:
            device = conn.device
            if _is_appium_device(device):
                import time

                appium_by = _appium_by()
                deadline = time.time() + max(timeout, 0)
                while True:
                    try:
                        el = device.find_element(appium_by.XPATH, xpath)
                        return PhoneElement(el, locator_desc=xpath, device=device)
                    except Exception:
                        if time.time() >= deadline:
                            raise BaseException(
                                PHONE_ELEMENT_NOT_FOUND_FORMAT.format(xpath),
                                "element not found",
                            )
                        time.sleep(0.5)
            selector = device.xpath(xpath)
            el = selector.wait(timeout) if hasattr(selector, "wait") else None
            if el is None:
                # wait()可能返回Selector自身/None, 兜底all()取首个
                all_els = selector.all()
                if not all_els:
                    raise BaseException(
                        PHONE_ELEMENT_NOT_FOUND_FORMAT.format(xpath),
                        "element not found",
                    )
                el = all_els[0]
            return PhoneElement(el, locator_desc=xpath, device=device)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def _element_center(element) -> tuple:
        """元素中心坐标: 兼容u2原生UiObject/XMLElement/Appium WebElement"""
        try:
            if hasattr(element, "bounds"):
                bounds = element.bounds
                if isinstance(bounds, dict):
                    return int((bounds["left"] + bounds["right"]) / 2), int((bounds["top"] + bounds["bottom"]) / 2)
                if isinstance(bounds, (tuple, list)) and len(bounds) == 4:
                    lx, ly, rx, ry = bounds
                    return int((lx + rx) / 2), int((ly + ry) / 2)
            if hasattr(element, "rect"):
                rect = element.rect  # Appium WebElement: {x, y, width, height}
                if isinstance(rect, dict) and "x" in rect:
                    return int(rect["x"] + rect["width"] / 2), int(rect["y"] + rect["height"] / 2)
            info = element.info or {}
            b = info.get("bounds", {})
            return int((b["left"] + b["right"]) / 2), int((b["top"] + b["bottom"]) / 2)
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def _element_bounds(element):
        """元素边界: 返回(left, top, right, bottom)"""
        try:
            if hasattr(element, "bounds"):
                bounds = element.bounds
                if isinstance(bounds, dict):
                    return bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]
                if isinstance(bounds, (tuple, list)) and len(bounds) == 4:
                    return tuple(bounds)
            if hasattr(element, "rect"):
                rect = element.rect  # Appium WebElement: {x, y, width, height}
                if isinstance(rect, dict) and "x" in rect:
                    return rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]
            info = element.info or {}
            b = info.get("bounds", {})
            return b["left"], b["top"], b["right"], b["bottom"]
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def _click_by_type(device, x: int, y: int, click_type: ClickType):
        click_type = _to_enum(click_type, ClickType)
        if _is_appium_device(device):
            script_map = {
                ClickType.DOUBLE: "mobile: doubleClickGesture",
                ClickType.LONG: "mobile: longClickGesture",
            }
            args = {"x": int(x), "y": int(y)}
            if click_type == ClickType.LONG:
                args["duration"] = 1000
            device.execute_script(script_map.get(click_type, "mobile: clickGesture"), args)
            return
        if click_type == ClickType.DOUBLE:
            device.double_click(x, y)
        elif click_type == ClickType.LONG:
            device.long_click(x, y, duration=1.0)
        else:
            device.click(x, y)

    @classmethod
    def click_element(cls, element: PhoneElement, click_type: ClickType = ClickType.SINGLE, after_delay: float = 0.5):
        """点击元素: 单击/双击/长按"""
        try:
            el = element.element
            click_type = _to_enum(click_type, ClickType)
            if hasattr(el, "click") and click_type == ClickType.SINGLE:
                el.click()
            else:
                device = getattr(element, "device", None) or getattr(el, "_d", None) or getattr(el, "device", None)
                if device is None:
                    raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format("元素对象缺少设备引用"), "no device ref")
                x, y = cls._element_center(el)
                cls._click_by_type(device, x, y, click_type)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @classmethod
    def click_screen(cls, conn: PhoneObject, x: int, y: int, click_type: ClickType = ClickType.SINGLE):
        """点击屏幕指定坐标"""
        try:
            cls._click_by_type(conn.device, int(x), int(y), click_type)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- 图像匹配 ----------

    @staticmethod
    def _screenshot_cv(device):
        """截屏为OpenCV BGR图像"""
        import cv2

        if _is_appium_device(device):
            import numpy as np

            png = device.get_screenshot_as_png()
            return cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        pil = device.screenshot()
        import numpy as np

        return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)

    @staticmethod
    def match_template_positions(screen_bgr, template_path: str, threshold: float = 0.8) -> list:
        """模板匹配, 返回[(cx, cy, w, h, score), ...]按分数降序"""
        import cv2

        tpl = cv2.imread(template_path)
        if tpl is None:
            raise BaseException(
                PHONE_IMAGE_ERROR_FORMAT.format("目标图像文件读取失败: {}".format(template_path)), "read fail"
            )
        sh, sw = screen_bgr.shape[:2]
        th, tw = tpl.shape[:2]
        if th > sh or tw > sw:
            return []
        result = cv2.matchTemplate(screen_bgr, tpl, cv2.TM_CCOEFF_NORMED)
        import numpy as np

        ys, xs = np.where(result >= threshold)
        cands = sorted(
            [(int(xs[i]), int(ys[i]), float(result[ys[i]][xs[i]])) for i in range(len(xs))],
            key=lambda p: -p[2],
        )
        kept = []
        for x, y, score in cands:
            cx, cy = x + tw // 2, y + th // 2
            if all(abs(cx - kx) >= tw or abs(cy - ky) >= th for kx, ky, _, _, _ in kept):
                kept.append((cx, cy, tw, th, score))
        return kept

    @classmethod
    def _match_on_screen(cls, conn: PhoneObject, template_path: str, threshold: float) -> list:
        return cls.match_template_positions(cls._screenshot_cv(conn.device), template_path, threshold)

    @classmethod
    def click_image(
        cls,
        conn: PhoneObject,
        img_path: str,
        click_type: ClickType = ClickType.SINGLE,
        x_ratio: float = 0.5,
        y_ratio: float = 0.5,
        threshold: float = 0.8,
    ):
        """图像匹配后点击第一个匹配位置"""
        positions = cls._match_on_screen(conn, img_path, threshold)
        if not positions:
            raise BaseException(PHONE_IMAGE_NOT_FOUND_FORMAT, "image not found")
        cx, cy, tw, th, _ = positions[0]
        x = int(cx + (x_ratio - 0.5) * tw)
        y = int(cy + (y_ratio - 0.5) * th)
        cls._click_by_type(conn.device, x, y, click_type)

    @classmethod
    def get_image_coords(
        cls,
        conn: PhoneObject,
        img_path: str,
        part: ImageTargetPart = ImageTargetPart.CENTER,
        x_ratio: float = 0.5,
        y_ratio: float = 0.5,
        threshold: float = 0.8,
    ) -> list:
        """获取图像坐标列表, 返回[[x, y], ...]"""
        import random

        positions = cls._match_on_screen(conn, img_path, threshold)
        if not positions:
            raise BaseException(PHONE_IMAGE_NOT_FOUND_FORMAT, "image not found")
        part = _to_enum(part, ImageTargetPart)
        coords = []
        for cx, cy, tw, th, _ in positions:
            if part == ImageTargetPart.CENTER:
                coords.append([cx, cy])
            elif part == ImageTargetPart.RANDOM:
                coords.append([int(cx + random.uniform(-0.4, 0.4) * tw), int(cy + random.uniform(-0.4, 0.4) * th)])
            else:
                coords.append([int(cx + (x_ratio - 0.5) * tw), int(cy + (y_ratio - 0.5) * th)])
        return coords

    @classmethod
    def wait_image(
        cls,
        conn: PhoneObject,
        img_paths: list,
        wait_type: WaitType = WaitType.APPEAR,
        all_images: bool = False,
        timeout: int = 20,
        threshold: float = 0.8,
    ) -> bool:
        """等待图像出现/消失"""
        import time

        if isinstance(img_paths, str):
            img_paths = [img_paths]
        paths = [str(p) for p in (img_paths or []) if str(p).strip()]
        if not paths:
            raise BaseException(PHONE_IMAGE_ERROR_FORMAT.format("请至少提供一张目标图像"), "no images")
        wait_type = _to_enum(wait_type, WaitType)
        deadline = time.time() + max(timeout, 0)
        while True:
            found = []
            for p in paths:
                try:
                    found.append(bool(cls._match_on_screen(conn, p, threshold)))
                except Exception:
                    found.append(False)
            if wait_type == WaitType.APPEAR:
                hit = all(found) if all_images else any(found)
                if hit:
                    return True
            else:
                gone = all(not f for f in found) if all_images else not any(found)
                if gone:
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.5)

    # ---------- 输入 ----------

    @classmethod
    def input_text(
        cls,
        conn: PhoneObject,
        element: PhoneElement,
        text: str,
        append: bool = False,
        press_enter: bool = False,
    ):
        """输入文本: 光标位置(需已聚焦)/指定输入框元素"""
        try:
            device = conn.device
            if _is_appium_device(device):
                if element is not None:
                    el = element.element
                    if not append:
                        el.clear()
                    el.send_keys(str(text))
                else:
                    device.switch_to.active_element.send_keys(str(text))
                if press_enter:
                    device.press_keycode(66)  # KEYCODE_ENTER
                return
            if element is not None:
                el = element.element
                if not append and hasattr(el, "clear_text"):
                    el.clear_text()
                if hasattr(el, "set_text"):
                    el.set_text(str(text))
                else:
                    x, y = cls._element_center(el)
                    conn.device.click(x, y)
                    conn.device.send_keys(str(text))
            else:
                conn.device.send_keys(str(text))
            if press_enter:
                conn.device.press("enter")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- 等待元素 ----------

    @classmethod
    def wait_element(cls, element: PhoneElement, wait_type: WaitType = WaitType.APPEAR, timeout: int = 20) -> bool:
        """等待元素出现/消失(element参数来自locate的元素对象, 内部持有xpath)"""
        import time

        wait_type = _to_enum(wait_type, WaitType)
        device = getattr(element, "device", None)
        xpath = getattr(element, "locator_desc", "")
        deadline = time.time() + max(timeout, 0)
        while True:
            if device is not None and _is_appium_device(device) and xpath:
                # Appium元素可能stale, 用xpath重新查询
                try:
                    exists = bool(device.find_elements(_appium_by().XPATH, xpath))
                except Exception:
                    exists = False
            else:
                el = element.element
                exists = bool(el)
                if hasattr(el, "exists"):
                    exists = bool(el.exists)
                elif hasattr(el, "attrib") and el.attrib is not None:
                    exists = True
            if wait_type == WaitType.APPEAR and exists:
                return True
            if wait_type == WaitType.DISAPPEAR and not exists:
                return True
            if time.time() >= deadline:
                return False
            time.sleep(0.5)

    # ---------- 滑动/按键 ----------

    @classmethod
    def swipe_screen(
        cls,
        conn: PhoneObject,
        mode: SwipeMode = SwipeMode.DIRECTION,
        direction: SwipeDirection = SwipeDirection.UP,
        sx: int = 0,
        sy: int = 0,
        ex: int = 0,
        ey: int = 0,
        duration: int = 300,
        element: PhoneElement = None,
    ):
        """滑动手机屏幕: 方向/坐标, 可限定元素区域内"""
        try:
            device = conn.device
            mode = _to_enum(mode, SwipeMode)
            if element is not None:
                left, top, right, bottom = cls._element_bounds(element.element)
            else:
                w, h = _window_size(device)
                left, top, right, bottom = 0, 0, w, h
            if mode == SwipeMode.DIRECTION:
                direction = _to_enum(direction, SwipeDirection)
                cx = (left + right) // 2
                if direction == SwipeDirection.UP:
                    start, end = (cx, top + int((bottom - top) * 0.8)), (cx, top + int((bottom - top) * 0.2))
                elif direction == SwipeDirection.DOWN:
                    start, end = (cx, top + int((bottom - top) * 0.2)), (cx, top + int((bottom - top) * 0.8))
                else:
                    cy = (top + bottom) // 2
                    if direction == SwipeDirection.LEFT:
                        start, end = (left + int((right - left) * 0.8), cy), (left + int((right - left) * 0.2), cy)
                    else:
                        start, end = (left + int((right - left) * 0.2), cy), (left + int((right - left) * 0.8), cy)
            else:
                start, end = (int(sx), int(sy)), (int(ex), int(ey))
            if _is_appium_device(device):
                _appium_swipe(device, *start, *end, duration=max(duration, 0))
            else:
                device.swipe(*start, *end, duration=max(duration, 0))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def press_key(conn: PhoneObject, key: KeyType = KeyType.HOME):
        """点击按键: 主页/后退/切换应用/回车确认"""
        key = _to_enum(key, KeyType)
        key_map = {
            KeyType.HOME: "home",
            KeyType.BACK: "back",
            KeyType.SWITCH_APP: "app_switch",
            KeyType.ENTER: "enter",
        }
        appium_keycode = {  # Android keycode
            KeyType.HOME: 3,
            KeyType.BACK: 4,
            KeyType.SWITCH_APP: 187,
            KeyType.ENTER: 66,
        }
        try:
            device = conn.device
            if _is_appium_device(device):
                device.press_keycode(appium_keycode[key])
            else:
                device.press(key_map[key])
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- 元素信息/截图 ----------

    @staticmethod
    def get_element_info(element: PhoneElement, info_type: str = "text", attr_name: str = "") -> str:
        """获取元素文本内容或属性值"""
        from . import ElementInfoType

        try:
            el = element.element
            if hasattr(el, "get_attribute") and not hasattr(el, "attrib"):
                # Appium WebElement
                if _to_enum(info_type, ElementInfoType) == ElementInfoType.TEXT:
                    return str(getattr(el, "text", "") or "")
                if not attr_name:
                    raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format("请填写属性名称"), "no attr name")
                alias = {"resourceId": "resourceId", "resource-id": "resourceId", "content-desc": "contentDescription"}
                return str(el.get_attribute(alias.get(attr_name, attr_name)) or "")
            info = {}
            if hasattr(el, "attrib"):
                info = dict(el.attrib or {})
            elif hasattr(el, "info"):
                info = dict(el.info or {})
            if _to_enum(info_type, ElementInfoType) == ElementInfoType.TEXT:
                text = info.get("text", "")
                if text == "" and hasattr(el, "get_text"):
                    text = el.get_text() or ""
                return str(text)
            if not attr_name:
                raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format("请填写属性名称"), "no attr name")
            if attr_name in info:
                return str(info[attr_name])
            alias = {"resourceId": "resource-id", "resource-id": "resourceId", "content-desc": "contentDescription"}
            key = alias.get(attr_name, attr_name)
            if key in info:
                return str(info[key])
            return ""
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def element_screenshot(conn: PhoneObject, element: PhoneElement, folder: str, filename: str = "") -> str:
        """元素截图并保存(整屏截图后按元素边界裁剪)"""
        import os
        import time

        try:
            left, top, right, bottom = PhoneCore._element_bounds(element.element)
            os.makedirs(folder, exist_ok=True)
            if not filename:
                filename = "phone_element_{}.png".format(int(time.time() * 1000))
            if not filename.lower().endswith(".png"):
                filename += ".png"
            target = os.path.join(folder, filename)
            device = conn.device
            if _is_appium_device(device):
                import io

                from PIL import Image

                pil = Image.open(io.BytesIO(device.get_screenshot_as_png())).convert("RGB")
                pil.crop((int(left), int(top), int(right), int(bottom))).save(target)
            else:
                pil = device.screenshot().convert("RGB")
                pil.crop((int(left), int(top), int(right), int(bottom))).save(target)
            return target
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_ELEMENT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def screenshot(conn: PhoneObject, folder: str, filename: str = "") -> str:
        """屏幕截图并保存"""
        import os
        import time

        try:
            os.makedirs(folder, exist_ok=True)
            if not filename:
                filename = "phone_screen_{}.png".format(int(time.time() * 1000))
            if not filename.lower().endswith(".png"):
                filename += ".png"
            target = os.path.join(folder, filename)
            device = conn.device
            if _is_appium_device(device):
                device.get_screenshot_as_file(target)
            else:
                device.screenshot(target)
            return target
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- App/剪贴板 ----------

    @staticmethod
    def open_close_app(conn: PhoneObject, action: AppActionType = AppActionType.OPEN, package: str = ""):
        """打开/关闭指定App"""
        if not package:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format("请填写App包名"), "no package")
        action = _to_enum(action, AppActionType)
        try:
            device = conn.device
            if _is_appium_device(device):
                if action == AppActionType.OPEN:
                    device.activate_app(package)
                else:
                    device.terminate_app(package)
            elif action == AppActionType.OPEN:
                device.app_start(package)
            else:
                device.app_stop(package)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def get_clipboard(conn: PhoneObject) -> str:
        """获取手机剪贴板文本(Appium模式兼容安卓9+)"""
        try:
            device = conn.device
            if _is_appium_device(device):
                return str(device.get_clipboard() or "")
            return str(device.clipboard or "")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format("获取剪贴板失败: {}".format(str(e))), str(e))

    @staticmethod
    def set_clipboard(conn: PhoneObject, text: str):
        """设置手机剪贴板文本(Appium模式兼容安卓9+)"""
        try:
            conn.device.set_clipboard(str(text))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format("设置剪贴板失败: {}".format(str(e))), str(e))

    # ---------- 屏幕/锁屏 ----------

    @staticmethod
    def rotate_screen(conn: PhoneObject, orientation: OrientationType = OrientationType.PORTRAIT):
        """旋转屏幕: 横屏/竖屏"""
        orientation = _to_enum(orientation, OrientationType)
        try:
            device = conn.device
            if _is_appium_device(device):
                device.orientation = "PORTRAIT" if orientation == OrientationType.PORTRAIT else "LANDSCAPE"
            else:
                device.orientation = "natural" if orientation == OrientationType.PORTRAIT else "left"
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def get_orientation(conn: PhoneObject) -> int:
        """获取屏幕方向: 0竖屏 1横屏"""
        try:
            device = conn.device
            if _is_appium_device(device):
                return 0 if "PORTRAIT" in str(device.orientation).upper() else 1
            return 0 if str(device.orientation) in ("natural", "right") else 1
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    @classmethod
    def unlock_device(cls, device, unlock_type: UnlockType = UnlockType.PASSWORD, unlock_secret: str = ""):
        """解锁手机: 亮屏→上滑→输入密码/画图案"""
        unlock_type = _to_enum(unlock_type, UnlockType)
        try:
            if _is_appium_device(device):
                cls._unlock_appium(device, unlock_type, unlock_secret)
                return
            device.screen_on()
            w, h = _window_size(device)
            device.swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.2), 300)
            if unlock_type == UnlockType.PASSWORD and unlock_secret:
                device.shell('input text "{}"'.format(unlock_secret.replace('"', "")))
                device.press("enter")
            elif unlock_type == UnlockType.PATTERN and unlock_secret:
                # 图案密码: 数字串如"5416", 映射3x3宫格中心点(屏幕中央60%区域)
                points = cls._pattern_points(w, h, unlock_secret)
                if points:
                    device.swipe_points(points, 300)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format("解锁失败: {}".format(str(e))), str(e))

    @staticmethod
    def _pattern_points(w: int, h: int, unlock_secret: str) -> list:
        """图案密码数字串映射3x3宫格中心点(屏幕中央60%区域)"""
        grid, size = [], 0.6
        left, top = w * (1 - size) / 2, h * (1 - size) / 2
        cw, ch = w * size / 2, h * size / 2
        for r in range(3):
            for c in range(3):
                grid.append((int(left + cw * c), int(top + ch * r)))
        return [grid[int(c) - 1] for c in str(unlock_secret) if c.isdigit() and 1 <= int(c) <= 9]

    @classmethod
    def _unlock_appium(cls, driver, unlock_type: UnlockType, unlock_secret: str):
        """Appium解锁: 唤醒→上滑→数字密码逐键/图案连线"""
        driver.press_keycode(224)  # KEYCODE_WAKEUP
        w, h = _window_size(driver)
        _appium_swipe(driver, w // 2, int(h * 0.8), w // 2, int(h * 0.2), 300)
        if unlock_type == UnlockType.PASSWORD and unlock_secret:
            for c in str(unlock_secret):
                if c.isdigit():
                    driver.press_keycode(7 + int(c))  # KEYCODE_0=7 ... KEYCODE_9=16
            driver.press_keycode(66)  # KEYCODE_ENTER
        elif unlock_type == UnlockType.PATTERN and unlock_secret:
            points = cls._pattern_points(w, h, unlock_secret)
            if len(points) >= 2:
                from selenium.webdriver.common.action_chains import ActionChains

                actions = ActionChains(driver)
                pointer = actions.w3c_actions.add_pointer_input("touch", "finger1")
                pointer.create_pointer_move(x=points[0][0], y=points[0][1], duration=0)
                pointer.create_pointer_down(button=0)
                for px, py in points[1:]:
                    pointer.create_pointer_move(x=px, y=py, duration=150)
                pointer.create_pointer_up(button=0)
                actions.perform()

    @classmethod
    def lock_unlock_screen(
        cls,
        conn: PhoneObject,
        action: ScreenActionType = ScreenActionType.UNLOCK,
        unlock_type: UnlockType = UnlockType.NONE,
        unlock_secret: str = "",
    ):
        """锁定/解锁屏幕"""
        action = _to_enum(action, ScreenActionType)
        try:
            device = conn.device
            if action == ScreenActionType.LOCK:
                if _is_appium_device(device):
                    device.lock()
                else:
                    device.screen_off()
            else:
                cls.unlock_device(
                    device,
                    unlock_type
                    if unlock_type != UnlockType.NONE
                    else UnlockType.PASSWORD
                    if unlock_secret
                    else UnlockType.NONE,
                    unlock_secret,
                )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- 文件 ----------

    @staticmethod
    def push_file(conn: PhoneObject, local_path: str, remote_path: str):
        """发送本地文件到手机"""
        try:
            device = conn.device
            if _is_appium_device(device):
                import base64

                with open(local_path, "rb") as f:
                    device.push_file(remote_path, base64.b64encode(f.read()).decode("utf-8"))
            else:
                device.push(local_path, remote_path)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_FILE_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    def pull_file(conn: PhoneObject, remote_path: str, local_path: str):
        """从手机拉取文件到本地"""
        import os

        try:
            parent = os.path.dirname(local_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            device = conn.device
            if _is_appium_device(device):
                import base64

                b64 = device.pull_file(remote_path)
                with open(local_path, "wb") as f:
                    f.write(base64.b64decode(b64))
            else:
                device.pull(remote_path, local_path)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_FILE_ERROR_FORMAT.format(str(e)), str(e))

    # ---------- UI树 ----------

    @staticmethod
    def get_ui_tree(conn: PhoneObject) -> str:
        """获取当前页面UI树(XML字符串)"""
        try:
            device = conn.device
            if _is_appium_device(device):
                return device.page_source
            return device.dump_hierarchy()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PHONE_EXECUTE_ERROR_FORMAT.format(str(e)), str(e))
