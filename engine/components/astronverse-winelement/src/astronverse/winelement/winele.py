import os
import time

import pyautogui
from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import WinPick
from astronverse.actionlib.utils import FileExistenceType, handle_existence, Credential
from astronverse.locator import PickerDomain, Point
from astronverse.winelement import (
    ElementContainTypeFlag,
    ElementInputType,
    MouseClickButton,
    MouseClickKeyboard,
    MouseClickType,
    WinLoopGetTypeFlag,
)
from astronverse.winelement.core import IWinEleCore
from astronverse.winelement.core_win import WinEleCore
from astronverse.winelement.error import *

WinEleCore: IWinEleCore = WinEleCore()


class WinEle:
    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
    )
    def click_element(
        pick: WinPick,
        click_button: MouseClickButton = MouseClickButton.LEFT,
        click_type: MouseClickType = MouseClickType.CLICK,
        wait_time: float = 10.0,
        horizontals_offset: int = 0,
        verticals_offset: int = 0,
        keyboard_input: MouseClickKeyboard = MouseClickKeyboard.NONE,
    ):
        locator = WinEleCore.find(pick, wait_time)
        point = locator.point()

        # 按下辅助按键
        if keyboard_input != MouseClickKeyboard.NONE:
            pyautogui.keyDown(keyboard_input.value)
        try:
            locator.move(Point(point.x + int(horizontals_offset), point.y + int(verticals_offset)))
            pyautogui.click(
                clicks=1 if click_type == MouseClickType.CLICK else 2,
                button=click_button.value,
            )
        except Exception as e:
            raise e
        finally:
            # 记得释放
            if keyboard_input != MouseClickKeyboard.NONE:
                pyautogui.keyUp(keyboard_input.value)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "file_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
        ],
    )
    def screenshot_element(
        pick: WinPick,
        file_path: str,
        file_name: str = "桌面元素截图",
        exist_type: FileExistenceType = FileExistenceType.RENAME,
    ):
        if not file_name.endswith(".png"):
            file_name += ".png"

        new_file_path = handle_existence(os.path.join(file_path, file_name), exist_type)
        if not new_file_path:
            raise BaseException(PATH_ERROR, "拾取或保存路径有误")

        locator = WinEleCore.find(pick=pick)
        window_rect = locator.rect()
        rect = (
            window_rect.left,
            window_rect.top,
            window_rect.width(),
            window_rect.height(),
        )
        screenshot = pyautogui.screenshot(region=rect)
        screenshot.save(new_file_path)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
    )
    def hover_element(pick: WinPick, wait_time: float = 10.0):
        locator = WinEleCore.find(pick, wait_time)
        locator.hover()

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "text",
                dynamics=[
                    DynamicsItem(
                        key="$this.text.show",
                        expression="return $this.input_type.value == '{}'".format(ElementInputType.KEYBOARD.value),
                    )
                ],
            ),
            atomicMg.param(
                "credential_text",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value, params={"filters": ["credential"]}),
                dynamics=[
                    DynamicsItem(
                        key="$this.credential_text.show",
                        expression=f"return $this.input_type.value == '{ElementInputType.Credential.value}'",
                    )
                ],
            ),
        ],
    )
    def input_text_element(
        pick: WinPick,
        input_type: ElementInputType = ElementInputType.KEYBOARD,
        text: str = "",
        credential_text: str = "",
        clear_first: bool = True,
        wait_time: float = 10.0,
    ):
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        locator = WinEleCore.find(pick, wait_time)
        locator.move()
        pyautogui.click()

        import uiautomation

        if clear_first:
            window_control = locator.control()
            if window_control.ControlTypeName == uiautomation.EditControl.ControlTypeName:
                window_control.GetValuePattern().SetValue("")
            else:
                pyautogui.press("home")
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("delete")
        else:
            pyautogui.press("end")

        if input_type == ElementInputType.KEYBOARD:
            uiautomation.SendKeys(text)
        elif input_type == ElementInputType.CLIPBOARD:
            pyautogui.hotkey("ctrl", "v")
        elif input_type == ElementInputType.Credential:
            uiautomation.SendKeys(Credential.get_credential(credential_text))

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[atomicMg.param("ele_text", types="Str")],
    )
    def get_element_text(pick: WinPick, wait_time: float = 10.0):
        locator = WinEleCore.find(pick, wait_time)
        return locator.control().Name

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        outputList=[
            atomicMg.param("get_similar_ele", types="List"),
        ],
    )
    def similar(pick: WinPick, wait_time: int = 10) -> list:
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        locator_list = WinEleCore.find(pick, wait_time)
        res_list = []
        if locator_list:
            if not isinstance(locator_list, list):
                locator_list = [locator_list]
            for locator in locator_list:
                win_pick = WinPick()
                win_pick.locator = locator
                res_list.append(win_pick)
        return res_list

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        noAdvanced=True,
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param("get_type", formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value)),
            atomicMg.param("start", types="Int"),
            atomicMg.param("end", types="Int"),
            atomicMg.param("wait_time", types="Float"),
        ],
        outputList=[
            atomicMg.param("index", types="Int"),
            atomicMg.param("item", types="Any"),
        ],
    )
    def loop_similar(
        pick: WinPick,
        get_type: WinLoopGetTypeFlag = WinLoopGetTypeFlag.GetElement,
        start: int = 0,
        end: int = -1,
        wait_time: float = 10.0,
    ):
        """循环相似元素（桌面窗口）"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        def get_iterator():
            locator_list = WinEleCore.find(pick, wait_time)
            if not locator_list:
                return
            if not isinstance(locator_list, list):
                locator_list = [locator_list]
            count = 0
            for locator in locator_list:
                if count < start:
                    count += 1
                    continue
                if 0 < end <= count:
                    return
                count += 1
                if get_type == WinLoopGetTypeFlag.GetElement:
                    win_pick = WinPick()
                    win_pick.locator = locator
                    item = win_pick
                else:
                    control = locator.control()
                    if get_type == WinLoopGetTypeFlag.GetText:
                        item = control.Name
                    else:  # GetValue
                        try:
                            item = control.GetValuePattern().Value
                        except Exception:
                            try:
                                item = control.GetLegacyIAccessiblePattern().Value
                            except Exception:
                                item = ""
                yield count, item

        return get_iterator()

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "check_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param("wait_time", types="Float"),
        ],
    )
    def contain_element(
        pick: WinPick,
        check_type: ElementContainTypeFlag = ElementContainTypeFlag.CONTAIN,
        wait_time: float = 10,
    ) -> bool:
        """
        判断窗口中是否包含指定元素
        """
        wait_time = max(0, float(wait_time))
        while wait_time >= 0:
            start = time.time()
            try:
                WinEleCore.find(pick=pick, wait_time=0)
                found = True
            except Exception:
                found = False
            if check_type == ElementContainTypeFlag.CONTAIN and found:
                return True
            if check_type == ElementContainTypeFlag.NOT_CONTAIN and not found:
                return True
            if time.time() - start >= wait_time:
                break
            time.sleep(0.3)
            wait_time = wait_time - (time.time() - start)
        return False
