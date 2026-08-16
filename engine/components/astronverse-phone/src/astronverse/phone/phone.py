"""手机自动化原子(Phone分类): 基于uiautomator2或Appium驱动安卓设备"""

import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
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
from .error import PHONE_NO_CONNECTION_FORMAT
from .phone_core import PhoneCore
from .phone_obj import PhoneElement, PhoneObject


class Phone:
    # ---------- 连接管理 ----------

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("target_type"),
            atomicMg.param(
                "serial",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.serial.show",
                        expression="return $this.target_type.value == 'specified'",
                    )
                ],
            ),
            atomicMg.param(
                "ignore_failed",
                dynamics=[
                    DynamicsItem(
                        key="$this.ignore_failed.show",
                        expression="return $this.target_type.value == 'all'",
                    )
                ],
            ),
            atomicMg.param(
                "custom_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
            atomicMg.param("connect_mode", types="ConnectMode"),
            atomicMg.param(
                "appium_server",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.appium_server.show",
                        expression="return $this.connect_mode.value == 'appium'",
                    )
                ],
            ),
            atomicMg.param("unlock_type"),
            atomicMg.param(
                "unlock_secret",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.unlock_secret.show",
                        expression="return $this.unlock_type.value != 'none'",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("conn_list", types="List"),
            atomicMg.param("failed_list", types="List"),
        ],
    )
    def connect(
        target_type="auto",
        serial: str = "",
        ignore_failed: bool = True,
        custom_name: str = "",
        connect_mode: ConnectMode = ConnectMode.UIAUTOMATOR2,
        appium_server: str = "http://127.0.0.1:4723",
        unlock_type: UnlockType = UnlockType.NONE,
        unlock_secret: str = "",
    ):
        """
        连接手机
        :param target_type: 连接对象(指定手机/运行时自动选择/所有已连接的手机)
        :param serial: 手机serial(指定手机时填写, 可通过【获取手机设备列表】查看)
        :param ignore_failed: 连接所有手机时, 是否忽略连接失败的手机
        :param custom_name: 自定义手机连接名称
        :param connect_mode: 连接模式(Uiautomator2直连/Appium服务, 安卓9+读写剪贴板需Appium模式)
        :param appium_server: Appium服务地址(Appium模式时填写, 如http://127.0.0.1:4723)
        :param unlock_type: 连接时自动解锁(无/数字密码/图案密码)
        :param unlock_secret: 手机密码(数字密码或图案数字串如5416)
        :return: 指定/自动模式返回连接对象; 全部模式返回(连接列表, 失败列表)
        """
        from . import ConnectTargetType

        from astronverse.phone.phone_core import _to_enum

        target_type = _to_enum(target_type, ConnectTargetType)
        if target_type == ConnectTargetType.ALL:
            return PhoneCore.connect_all(
                ignore_failed, custom_name, unlock_type, unlock_secret, connect_mode, appium_server
            )
        return PhoneCore.connect(
            "" if target_type == ConnectTargetType.AUTO else serial,
            custom_name,
            unlock_type,
            unlock_secret,
            connect_mode,
            appium_server,
        )

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject")],
        outputList=[],
    )
    def disconnect(conn: PhoneObject = None):
        """
        断开手机连接
        :param conn: 手机连接对象
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.disconnect(conn)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject")],
        outputList=[atomicMg.param("info", types="Dict")],
    )
    def get_connect_info(conn: PhoneObject = None) -> dict:
        """
        获取手机连接详情
        :param conn: 手机连接对象
        :return: 连接详情字典(platform/platformName/platformVersion/deviceUDID/deviceScreenSize/deviceModel/deviceManufacturer/custom_name)
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.get_connect_info(conn)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[],
        outputList=[atomicMg.param("device_list", types="List")],
    )
    def get_devices() -> list:
        """
        获取手机设备列表
        :return: adb已连接的手机serial列表
        """
        return PhoneCore.list_devices()

    # ---------- 元素操作 ----------

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("by"),
            atomicMg.param(
                "value",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("index", types="Int"),
            atomicMg.param("timeout", types="Int"),
        ],
        outputList=[atomicMg.param("element", types="PhoneElement")],
    )
    def get_element(
        conn: PhoneObject = None, by: LocatorType = LocatorType.ID, value: str = "", index: int = 0, timeout: int = 10
    ):
        """
        获取手机元素对象
        :param conn: 手机连接对象
        :param by: 定位方式(id/text/text_contains/description/xpath/selector/class)
        :param value: 元素特征(定位方式对应的值, selector传JSON字典)
        :param index: 第N个匹配元素(从0开始)
        :param timeout: 等待元素出现超时秒数
        :return: 元素对象
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.locate(conn, by, value, index, timeout)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("element", types="PhoneElement"),
            atomicMg.param("by"),
            atomicMg.param(
                "value",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
            atomicMg.param("index", types="Int"),
            atomicMg.param("click_type"),
            atomicMg.param("after_delay", types="Float"),
        ],
        outputList=[],
    )
    def click_element(
        conn: PhoneObject = None,
        element: PhoneElement = None,
        by: LocatorType = LocatorType.ID,
        value: str = "",
        index: int = 0,
        click_type: ClickType = ClickType.SINGLE,
        after_delay: float = 0.5,
    ):
        """
        点击元素(手机)
        :param conn: 手机连接对象
        :param element: 元素对象(与定位方式二选一)
        :param by: 定位方式(未传元素对象时生效)
        :param value: 元素特征
        :param index: 第N个匹配元素(从0开始)
        :param click_type: 点击方式(单击/双击/长按)
        :param after_delay: 执行后延迟秒数
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        if element is None:
            element = PhoneCore.locate(conn, by, value, index)
        PhoneCore.click_element(element, click_type)
        if after_delay > 0:
            time.sleep(after_delay)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("position_type"),
            atomicMg.param(
                "x",
                types="Int",
                dynamics=[DynamicsItem(key="$this.x.show", expression="return $this.position_type.value == 'coord'")],
            ),
            atomicMg.param(
                "y",
                types="Int",
                dynamics=[DynamicsItem(key="$this.y.show", expression="return $this.position_type.value == 'coord'")],
            ),
            atomicMg.param(
                "img_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
                dynamics=[
                    DynamicsItem(key="$this.img_path.show", expression="return $this.position_type.value == 'image'")
                ],
            ),
            atomicMg.param("click_type"),
            atomicMg.param("threshold", types="Float"),
            atomicMg.param("after_delay", types="Float"),
        ],
        outputList=[],
    )
    def click_screen(
        conn: PhoneObject = None,
        position_type: PositionType = PositionType.COORD,
        x: int = 0,
        y: int = 0,
        img_path: str = "",
        click_type: ClickType = ClickType.SINGLE,
        threshold: float = 0.8,
        after_delay: float = 0.5,
    ):
        """
        点击屏幕(手机)
        :param conn: 手机连接对象
        :param position_type: 点击位置(通过坐标指定/通过图像匹配)
        :param x: 横坐标(相对屏幕左上角)
        :param y: 纵坐标(相对屏幕左上角)
        :param img_path: 目标图像(图像匹配模式, 点击第一个匹配位置)
        :param click_type: 点击方式(单击/双击/长按)
        :param threshold: 图像匹配置信度阈值(0-1)
        :param after_delay: 执行后延迟秒数
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        from astronverse.phone.phone_core import _to_enum

        if _to_enum(position_type, PositionType) == PositionType.IMAGE:
            PhoneCore.click_image(conn, img_path, click_type, threshold=threshold)
        else:
            PhoneCore.click_screen(conn, x, y, click_type)
        if after_delay > 0:
            time.sleep(after_delay)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "img_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
                required=True,
            ),
            atomicMg.param("part"),
            atomicMg.param("x_ratio", types="Float"),
            atomicMg.param("y_ratio", types="Float"),
            atomicMg.param("threshold", types="Float"),
        ],
        outputList=[atomicMg.param("coords", types="List")],
    )
    def get_image_coords(
        conn: PhoneObject = None,
        img_path: str = "",
        part: ImageTargetPart = ImageTargetPart.CENTER,
        x_ratio: float = 0.5,
        y_ratio: float = 0.5,
        threshold: float = 0.8,
    ) -> list:
        """
        获取图像坐标(手机)
        :param conn: 手机连接对象
        :param img_path: 目标图像
        :param part: 目标图像部位(中心点/随机位置/自定义)
        :param x_ratio: 自定义部位横向比例(0-1, 图像区域内相对位置)
        :param y_ratio: 自定义部位纵向比例(0-1)
        :param threshold: 匹配置信度阈值(0-1)
        :return: 图像位置列表[[x, y], ...]
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.get_image_coords(conn, img_path, part, x_ratio, y_ratio, threshold)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param("input_target"),
            atomicMg.param("element", types="PhoneElement"),
            atomicMg.param("append", types="Bool"),
            atomicMg.param("press_enter", types="Bool"),
            atomicMg.param("after_delay", types="Float"),
        ],
        outputList=[],
    )
    def input_text(
        conn: PhoneObject = None,
        text: str = "",
        input_target: InputTargetType = InputTargetType.CURSOR,
        element: PhoneElement = None,
        append: bool = False,
        press_enter: bool = False,
        after_delay: float = 0.5,
    ):
        """
        输入文本(手机)
        :param conn: 手机连接对象
        :param text: 输入内容
        :param input_target: 输入对象(光标所在位置需先聚焦/指定输入框元素)
        :param element: 输入框元素对象
        :param append: 是否追加输入(否则清空后输入)
        :param press_enter: 输入后是否回车
        :param after_delay: 执行后延迟秒数
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        from astronverse.phone.phone_core import _to_enum

        if _to_enum(input_target, InputTargetType) == InputTargetType.ELEMENT and element is None:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "请提供输入框元素对象")
        PhoneCore.input_text(conn, element, text, append, press_enter)
        if after_delay > 0:
            time.sleep(after_delay)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("element", types="PhoneElement"),
            atomicMg.param("wait_type"),
            atomicMg.param("timeout", types="Int"),
        ],
        outputList=[atomicMg.param("result", types="Bool")],
    )
    def wait_element(
        conn: PhoneObject = None,
        element: PhoneElement = None,
        wait_type: WaitType = WaitType.APPEAR,
        timeout: int = 20,
    ) -> bool:
        """
        等待元素(手机)
        :param conn: 手机连接对象
        :param element: 元素对象(通过【获取手机元素对象】获取)
        :param wait_type: 等待方式(出现/消失)
        :param timeout: 超时秒数
        :return: 超时时间内状态符合返回True
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        if element is None:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "请提供元素对象")
        return PhoneCore.wait_element(element, wait_type, timeout)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "img_paths",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param("wait_type"),
            atomicMg.param("all_images", types="Bool"),
            atomicMg.param("timeout", types="Int"),
            atomicMg.param("threshold", types="Float"),
        ],
        outputList=[atomicMg.param("result", types="Bool")],
    )
    def wait_image(
        conn: PhoneObject = None,
        img_paths: list = None,
        wait_type: WaitType = WaitType.APPEAR,
        all_images: bool = False,
        timeout: int = 20,
        threshold: float = 0.8,
    ) -> bool:
        """
        等待图像(手机)
        :param conn: 手机连接对象
        :param img_paths: 目标图像路径列表(支持单个路径字符串)
        :param wait_type: 等待方式(出现/消失)
        :param all_images: 是否等待全部图像符合条件
        :param timeout: 超时秒数
        :param threshold: 匹配置信度阈值(0-1)
        :return: 超时时间内状态符合返回True
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.wait_image(conn, img_paths or [], wait_type, all_images, timeout, threshold)

    # ---------- 屏幕操作 ----------

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("mode"),
            atomicMg.param(
                "direction",
                dynamics=[
                    DynamicsItem(key="$this.direction.show", expression="return $this.mode.value == 'direction'")
                ],
            ),
            atomicMg.param(
                "element",
                types="PhoneElement",
                dynamics=[DynamicsItem(key="$this.element.show", expression="return $this.area.value == 'element'")],
            ),
            atomicMg.param("area"),
            atomicMg.param(
                "sx",
                types="Int",
                dynamics=[DynamicsItem(key="$this.sx.show", expression="return $this.mode.value == 'coord'")],
            ),
            atomicMg.param(
                "sy",
                types="Int",
                dynamics=[DynamicsItem(key="$this.sy.show", expression="return $this.mode.value == 'coord'")],
            ),
            atomicMg.param(
                "ex",
                types="Int",
                dynamics=[DynamicsItem(key="$this.ex.show", expression="return $this.mode.value == 'coord'")],
            ),
            atomicMg.param(
                "ey",
                types="Int",
                dynamics=[DynamicsItem(key="$this.ey.show", expression="return $this.mode.value == 'coord'")],
            ),
            atomicMg.param("duration", types="Int"),
            atomicMg.param("after_delay", types="Float"),
        ],
        outputList=[],
    )
    def swipe_screen(
        conn: PhoneObject = None,
        mode: SwipeMode = SwipeMode.DIRECTION,
        direction: SwipeDirection = SwipeDirection.UP,
        element: PhoneElement = None,
        area: SwipeAreaType = SwipeAreaType.SCREEN,
        sx: int = 0,
        sy: int = 0,
        ex: int = 0,
        ey: int = 0,
        duration: int = 300,
        after_delay: float = 0.5,
    ):
        """
        滑动手机屏幕
        :param conn: 手机连接对象
        :param mode: 滑动方式(方向/坐标)
        :param direction: 滑动方向(上/下/左/右)
        :param element: 滑动区域限定元素(滑动区域选择"指定元素"时)
        :param area: 滑动区域(整个屏幕/指定元素)
        :param sx: 起始点横坐标
        :param sy: 起始点纵坐标
        :param ex: 结束点横坐标
        :param ey: 结束点纵坐标
        :param duration: 滑动时间(毫秒)
        :param after_delay: 执行后延迟秒数
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        from astronverse.phone.phone_core import _to_enum

        if _to_enum(area, SwipeAreaType) == SwipeAreaType.ELEMENT and element is None:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "滑动区域为指定元素时, 请提供元素对象")
        PhoneCore.swipe_screen(conn, mode, direction, sx, sy, ex, ey, duration, element)
        if after_delay > 0:
            time.sleep(after_delay)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("key_name"),
            atomicMg.param("after_delay", types="Float"),
        ],
        outputList=[],
    )
    def press_key(conn: PhoneObject = None, key_name: KeyType = KeyType.HOME, after_delay: float = 0.5):
        """
        点击按键
        :param conn: 手机连接对象
        :param key_name: 按键(主页/后退/切换应用/回车确认)
        :param after_delay: 执行后延迟秒数
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.press_key(conn, key_name)
        if after_delay > 0:
            time.sleep(after_delay)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "folder_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
                required=True,
            ),
            atomicMg.param(
                "filename",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[atomicMg.param("file_path", types="Str")],
    )
    def screenshot(conn: PhoneObject = None, folder_path: str = "", filename: str = "") -> str:
        """
        屏幕截图(手机)
        :param conn: 手机连接对象
        :param folder_path: 保存文件夹
        :param filename: 文件名(可为空, 自动时间戳命名)
        :return: 截图完整路径
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.screenshot(conn, folder_path, filename)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("element", types="PhoneElement", required=True),
            atomicMg.param(
                "folder_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
                required=True,
            ),
            atomicMg.param(
                "filename",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[atomicMg.param("file_path", types="Str")],
    )
    def element_screenshot(
        conn: PhoneObject = None, element: PhoneElement = None, folder_path: str = "", filename: str = ""
    ) -> str:
        """
        元素截图(手机)
        :param conn: 手机连接对象
        :param element: 元素对象
        :param folder_path: 保存文件夹
        :param filename: 文件名(可为空, 自动时间戳命名)
        :return: 截图完整路径
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        if element is None:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "请提供元素对象")
        return PhoneCore.element_screenshot(conn, element, folder_path, filename)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("element", types="PhoneElement", required=True),
            atomicMg.param("info_type"),
            atomicMg.param(
                "attr_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[atomicMg.param("info", types="Str")],
    )
    def get_element_info(element: PhoneElement = None, info_type: str = "text", attr_name: str = "") -> str:
        """
        获取手机元素信息
        :param element: 元素对象
        :param info_type: 操作(获取元素文本内容/获取元素属性)
        :param attr_name: 属性名(text/contentDescription/className/bounds/resourceId/clickable等)
        :return: 元素信息
        """
        if element is None:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "请提供元素对象")
        return PhoneCore.get_element_info(element, info_type, attr_name)

    # ---------- App/剪贴板/方向 ----------

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("action"),
            atomicMg.param(
                "package",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[],
    )
    def open_close_app(conn: PhoneObject = None, action: AppActionType = AppActionType.OPEN, package: str = ""):
        """
        打开/关闭手机App
        :param conn: 手机连接对象
        :param action: 操作(打开/关闭)
        :param package: App包名(如com.tencent.mm)
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.open_close_app(conn, action, package)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject")],
        outputList=[atomicMg.param("text", types="Str")],
    )
    def get_clipboard(conn: PhoneObject = None) -> str:
        """
        获取手机剪切板文本
        :param conn: 手机连接对象
        :return: 剪贴板文本
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.get_clipboard(conn)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
        outputList=[],
    )
    def set_clipboard(conn: PhoneObject = None, text: str = ""):
        """
        发送文本到剪贴板(手机)
        :param conn: 手机连接对象
        :param text: 剪贴板文本内容
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.set_clipboard(conn, text)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject"), atomicMg.param("orientation")],
        outputList=[],
    )
    def rotate_screen(conn: PhoneObject = None, orientation: OrientationType = OrientationType.PORTRAIT):
        """
        旋转手机屏幕
        :param conn: 手机连接对象
        :param orientation: 屏幕方向(横屏/竖屏)
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.rotate_screen(conn, orientation)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject")],
        outputList=[atomicMg.param("orientation", types="Int")],
    )
    def get_orientation(conn: PhoneObject = None) -> int:
        """
        获取手机屏幕方向
        :param conn: 手机连接对象
        :return: 0竖屏 1横屏
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.get_orientation(conn)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param("action"),
            atomicMg.param("unlock_type"),
            atomicMg.param(
                "unlock_secret",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.unlock_secret.show",
                        expression="return $this.action.value == 'unlock' && $this.unlock_type.value != 'none'",
                    )
                ],
            ),
        ],
        outputList=[],
    )
    def lock_unlock_screen(
        conn: PhoneObject = None,
        action: ScreenActionType = ScreenActionType.UNLOCK,
        unlock_type: UnlockType = UnlockType.PASSWORD,
        unlock_secret: str = "",
    ):
        """
        锁定屏幕及解锁
        :param conn: 手机连接对象
        :param action: 操作(锁定/解锁)
        :param unlock_type: 解锁方式(无/数字密码/图案密码)
        :param unlock_secret: 手机密码(数字密码或图案数字串如5416)
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.lock_unlock_screen(conn, action, unlock_type, unlock_secret)

    # ---------- 文件/UI树 ----------

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "local_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
                required=True,
            ),
            atomicMg.param(
                "remote_path",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[],
    )
    def push_file(conn: PhoneObject = None, local_path: str = "", remote_path: str = ""):
        """
        发送文件到手机
        :param conn: 手机连接对象
        :param local_path: 本地文件路径
        :param remote_path: 手机存储位置路径(如/sdcard/dcim/camera/图片.png)
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.push_file(conn, local_path, remote_path)

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[
            atomicMg.param("conn", types="PhoneObject"),
            atomicMg.param(
                "remote_path",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "local_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("file_path", types="Str")],
    )
    def pull_file(conn: PhoneObject = None, remote_path: str = "", local_path: str = ""):
        """
        获取手机文件
        :param conn: 手机连接对象
        :param remote_path: 手机文件路径(如/sdcard/dcim/camera/图片.png)
        :param local_path: 本地保存位置
        :return: 本地文件路径
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        PhoneCore.pull_file(conn, remote_path, local_path)
        return local_path

    @staticmethod
    @atomicMg.atomic(
        "Phone",
        inputList=[atomicMg.param("conn", types="PhoneObject")],
        outputList=[atomicMg.param("ui_tree", types="Str")],
    )
    def get_ui_tree(conn: PhoneObject = None) -> str:
        """
        获取手机UI树
        :param conn: 手机连接对象
        :return: 当前页面XML结构字符串
        """
        if not conn:
            raise BaseException(PHONE_NO_CONNECTION_FORMAT, "conn is None")
        return PhoneCore.get_ui_tree(conn)
