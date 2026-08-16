import platform
import sys
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import WinPick
from astronverse.window import WindowExistType, WindowInfoTypeFlag, WindowVisibleTypeFlag
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

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
        ],
        outputList=[atomicMg.param("window_obj", types="WinPick")],
    )
    def get(pick: WinPick, wait_time: float = 10.0):
        """
        get 获取窗口对象并保存至变量，供后续窗口指令直接调用
        """
        deadline = time.time() + max(0, wait_time)
        while True:
            try:
                WindowsCore.find(pick)
                break
            except Exception:
                if time.time() >= deadline:
                    raise
                time.sleep(0.5)
        window_obj = WinPick(pick)
        window_obj.locator = None
        return window_obj

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
            atomicMg.param(
                "info_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
        outputList=[atomicMg.param("window_info", types="Any")],
    )
    def get_info(
        pick: WinPick,
        info_type: WindowInfoTypeFlag = WindowInfoTypeFlag.TITLE,
    ):
        """
        get_info 获取窗口信息（标题/类名/进程名/位置尺寸）
        """
        handler = WindowsCore.find(pick)
        return WindowsCore.info_value(handler, info_type)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param("title_contains"),
        ],
        outputList=[
            atomicMg.param("window_obj_list", types="List"),
            atomicMg.param("window_count", types="Int"),
        ],
    )
    def get_list(title_contains: str = ""):
        """
        get_list 获取所有满足标题条件的窗口对象列表
        """
        window_list = WindowsCore.find_list(title_contains)
        result = []
        for title, cls_name in window_list:
            win_pick = WinPick()
            win_pick["name"] = title
            win_pick["elementData"] = {"type": "uia", "path": [{"name": title, "cls": cls_name}]}
            result.append(win_pick)
        return result, len(result)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
            atomicMg.param("x", types="Int"),
            atomicMg.param("y", types="Int"),
        ],
    )
    def move(pick: WinPick, x: int = 0, y: int = 0):
        """
        move 移动窗口至屏幕指定位置
        """
        handler = WindowsCore.find(pick)
        return WindowsCore.move(handler, x, y)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "WINDOW"}),
            ),
            atomicMg.param(
                "visible_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
    )
    def set_visible(pick: WinPick, visible_type: WindowVisibleTypeFlag = WindowVisibleTypeFlag.SHOW):
        """
        set_visible 设置窗口显示或隐藏
        """
        handler = WindowsCore.find(pick)
        return WindowsCore.set_visible(handler, visible_type)

    @staticmethod
    @atomicMg.atomic(
        "Window",
        noAdvanced=True,
        inputList=[atomicMg.param("wait_time", types="Float")],
        outputList=[atomicMg.param("selected_text", types="Str")],
    )
    def get_selected_text(wait_time: float = 1.0):
        """
        get_selected_text 获取当前激活窗口中被选中的文本
        """
        deadline = time.time() + max(0, wait_time)
        while True:
            text = WindowsCore.get_selected_text()
            if text:
                return text
            if time.time() >= deadline:
                return text
            time.sleep(0.3)
