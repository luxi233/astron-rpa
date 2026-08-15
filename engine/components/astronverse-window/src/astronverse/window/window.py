import platform
import sys
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import WinPick
from astronverse.window import WindowExistType
from astronverse.window.core import IWindowsCore, WindowSizeType
from astronverse.window.error import *

if sys.platform == "win32":
    from astronverse.window.core_win import WindowsCore
elif platform.system() == "Linux":
    from astronverse.window.core_unix import WindowsCore
else:
    raise NotImplementedError("Your platform (%s) is not supported by (%s)." % (platform.system(), "clipboard"))

WindowsCore: IWindowsCore = WindowsCore()


class Window:
    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
            atomicMg.param(
                "check_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
    )
    def exist(
        pick: WinPick,
        check_type: WindowExistType = WindowExistType.EXIST,
        wait_time: float = 0,
    ) -> bool:
        """
        exist 窗口是否存在/不存在/激活/未激活
        """
        wait_time = max(0, wait_time)
        while wait_time >= 0:
            try:
                if check_type in (WindowExistType.ACTIVE, WindowExistType.NOT_ACTIVE):
                    handler = WindowsCore.find(pick)
                    if handler is None:
                        # 窗口不存在：谈不上激活，视为未激活
                        if check_type == WindowExistType.NOT_ACTIVE:
                            return True
                    else:
                        is_active = WindowsCore.is_active(handler)
                        if check_type == WindowExistType.ACTIVE and is_active:
                            return True
                        if check_type == WindowExistType.NOT_ACTIVE and not is_active:
                            return True
                else:
                    window_found = WindowsCore.find(pick) is not None
                    if window_found and check_type == WindowExistType.EXIST:
                        return True
            except Exception:
                if check_type in (WindowExistType.NOT_EXIST, WindowExistType.NOT_ACTIVE):
                    return True
            wait_time -= 0.5
            time.sleep(0.5)
        return False

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
        ],
    )
    def top(pick: WinPick):
        """
        top 置顶
        """
        handler = WindowsCore.find(pick)
        return WindowsCore.top(handler)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
        ],
    )
    def close(pick: WinPick):
        """
        close 关闭窗口
        """
        handler = WindowsCore.find(pick)
        return WindowsCore.close(handler)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
            atomicMg.param(
                "width",
                dynamics=[
                    DynamicsItem(
                        key="$this.width.show",
                        expression="return $this.size_type.value == '{}'".format(WindowSizeType.CUSTOM.value),
                    )
                ],
            ),
            atomicMg.param(
                "height",
                dynamics=[
                    DynamicsItem(
                        key="$this.height.show",
                        expression="return $this.size_type.value == '{}'".format(WindowSizeType.CUSTOM.value),
                    )
                ],
            ),
        ],
    )
    def set_size(
        pick: WinPick,
        size_type: WindowSizeType = WindowSizeType.MAX,
        width: int = 0,
        height: int = 0,
    ):
        """
        set_size 设置尺寸
        """
        if size_type == WindowSizeType.CUSTOM:
            if width <= 0 or height <= 0:
                raise BaseException(
                    PARAMETER_INVALID_FORMAT.format((width, height)),
                    "参数异常 {}".format((width, height)),
                )
        handler = WindowsCore.find(pick)
        return WindowsCore.size(handler, size_type, width, height)
