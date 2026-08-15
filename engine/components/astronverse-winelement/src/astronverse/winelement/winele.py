import os
import random
import time

import pyautogui
from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.humansim import human_sim
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


def _send_keys_human(text: str):
    """模拟真人区间内逐字符随机间隔输入，区间外一次性发送"""
    import uiautomation

    text = str(text)
    if not text:
        return
    if not human_sim.active:
        uiautomation.SendKeys(text)
        return
    for char in text:
        uiautomation.SendKeys(char, interval=0)
        time.sleep(random.uniform(0, 0.1))


def _get_element_attribute(control, attribute_name: str, index: int):
    """获取桌面元素属性；index 返回元素在相似元素组中的位置（从0开始）"""
    if not attribute_name:
        return ""
    if attribute_name == "index":
        return index
    return getattr(control, attribute_name, "")


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

        # 模拟真人：操作前随机停顿 + 点击坐标随机偏移
        human_sim.pre_action_pause()
        target_x = point.x + int(horizontals_offset)
        target_y = point.y + int(verticals_offset)
        if human_sim.should_jitter_click():
            target_x = human_sim.jitter(target_x)
            target_y = human_sim.jitter(target_y)

        # 按下辅助按键
        if keyboard_input != MouseClickKeyboard.NONE:
            pyautogui.keyDown(keyboard_input.value)
        try:
            locator.move(Point(target_x, target_y))
            pyautogui.click(
                clicks=1 if click_type == MouseClickType.CLICK else 2,
                button=click_button.value,
                interval=human_sim.click_interval(),
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
        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()
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
        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()
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
            _send_keys_human(text)
        elif input_type == ElementInputType.CLIPBOARD:
            pyautogui.hotkey("ctrl", "v")
        elif input_type == ElementInputType.Credential:
            _send_keys_human(Credential.get_credential(credential_text))

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
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param("get_type", formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value)),
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression="return $this.get_type.value == '{}'".format(WinLoopGetTypeFlag.GetAttribute.value),
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("get_similar_ele", types="List"),
            atomicMg.param("similar_count", types="Int"),
        ],
    )
    def similar(
        pick: WinPick,
        get_type: WinLoopGetTypeFlag = WinLoopGetTypeFlag.GetElement,
        attribute_name: str = "",
        wait_time: int = 10,
    ):
        """获取相似元素列表（桌面窗口）"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        locator_list = WinEleCore.find(pick, wait_time)
        res_list = []
        if locator_list:
            if not isinstance(locator_list, list):
                locator_list = [locator_list]
            for i, locator in enumerate(locator_list):
                if get_type == WinLoopGetTypeFlag.GetElement:
                    win_pick = WinPick()
                    win_pick.locator = locator
                    item = win_pick
                else:
                    control = locator.control()
                    if get_type == WinLoopGetTypeFlag.GetText:
                        item = control.Name
                    elif get_type == WinLoopGetTypeFlag.GetValue:
                        try:
                            item = control.GetValuePattern().Value
                        except Exception:
                            try:
                                item = control.GetLegacyIAccessiblePattern().Value
                            except Exception:
                                item = ""
                    else:  # GetAttribute
                        item = _get_element_attribute(control, attribute_name, i)
                res_list.append(item)
        return res_list, len(res_list)

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
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression="return $this.get_type.value == '{}'".format(WinLoopGetTypeFlag.GetAttribute.value),
                    )
                ],
            ),
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
        attribute_name: str = "",
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
                    elif get_type == WinLoopGetTypeFlag.GetValue:
                        try:
                            item = control.GetValuePattern().Value
                        except Exception:
                            try:
                                item = control.GetLegacyIAccessiblePattern().Value
                            except Exception:
                                item = ""
                    else:  # GetAttribute
                        item = _get_element_attribute(control, attribute_name, count - 1)
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
