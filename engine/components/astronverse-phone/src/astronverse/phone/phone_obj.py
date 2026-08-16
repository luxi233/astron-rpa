from typing import Any

from astronverse.actionlib.error import *


class PhoneObject:
    """手机连接对象(包装uiautomator2的Device或Appium的WebDriver)"""

    def __init__(self, device: Any, serial: str = "", custom_name: str = "", mode: str = "u2"):
        self.device = device
        self.serial = serial
        self.custom_name = custom_name
        self.mode = mode  # "u2" | "appium"

    @classmethod
    def __validate__(cls, name: str, value):
        if isinstance(value, PhoneObject):
            return value
        raise BaseException(
            PARAM_VERIFY_ERROR_FORMAT.format(name, value),
            f"{name}参数验证失败{value}",
        )


class PhoneElement:
    """手机元素对象(包装uiautomator2定位到的元素)"""

    def __init__(self, element: Any, locator_desc: str = "", device: Any = None):
        self.element = element
        self.locator_desc = locator_desc
        self.device = device

    @classmethod
    def __validate__(cls, name: str, value):
        if isinstance(value, PhoneElement):
            return value
        raise BaseException(
            PARAM_VERIFY_ERROR_FORMAT.format(name, value),
            f"{name}参数验证失败{value}",
        )
