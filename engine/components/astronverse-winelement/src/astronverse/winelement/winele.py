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
    DragTypeFlag,
    ElementCheckedTypeFlag,
    ElementContainTypeFlag,
    ElementInfoTypeFlag,
    ElementInputType,
    ElementSelectTypeFlag,
    ElementWaitTypeFlag,
    MouseClickButton,
    MouseClickKeyboard,
    MouseClickType,
    PositionRelativeToFlag,
    RelativeTypeFlag,
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

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "item_text",
                dynamics=[
                    DynamicsItem(
                        key="$this.item_text.show",
                        expression="return $this.select_type.value == '{}'".format(ElementSelectTypeFlag.BY_TEXT.value),
                    )
                ],
            ),
            atomicMg.param(
                "item_index",
                dynamics=[
                    DynamicsItem(
                        key="$this.item_index.show",
                        expression="return $this.select_type.value == '{}'".format(
                            ElementSelectTypeFlag.BY_INDEX.value
                        ),
                    )
                ],
            ),
        ],
    )
    def set_select(
        pick: WinPick,
        select_type: ElementSelectTypeFlag = ElementSelectTypeFlag.BY_TEXT,
        item_text: str = "",
        item_index: int = 1,
        wait_time: float = 10.0,
    ):
        """设置下拉框（桌面）：按选项内容或选项位置选择"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        control = WinEleCore.find(pick, wait_time).control()

        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()

        # 1. 展开下拉框（组合框需先展开）
        expanded = False
        try:
            expand_pattern = control.GetExpandCollapsePattern()
            if expand_pattern.ExpandState == 0:  # Collapsed
                expand_pattern.Expand()
                expanded = True
                time.sleep(0.3)
        except Exception:
            pass

        # 2. 定位选项列表容器（元素本身为List或展开后的父级下的List）
        list_control = None
        if control.ControlTypeName == "ListControl":
            list_control = control
        else:
            try:
                import uiautomation

                parent = control.GetParentControl()
                search_root = parent if parent else control
                list_control = uiautomation.ListControl(searchDepth=8, searchFromControl=search_root)
                if not list_control or not list_control.Exists(1, 0.5):
                    list_control = None
            except Exception:
                list_control = None

        def _select_item(item_control):
            try:
                item_control.GetSelectionItemPattern().Select()
                return True
            except Exception:
                # 兜底：点击选项
                try:
                    rect = item_control.BoundingRectangle
                    center_x = rect.left + (rect.right - rect.left) // 2
                    center_y = rect.top + (rect.bottom - rect.top) // 2
                    pyautogui.click(center_x, center_y)
                    return True
                except Exception:
                    return False

        selected = False
        if list_control:
            children = list_control.GetChildren()
            if select_type == ElementSelectTypeFlag.BY_INDEX:
                idx = int(item_index) - 1
                if 0 <= idx < len(children):
                    selected = _select_item(children[idx])
            else:
                target = str(item_text)
                for child in children:
                    if target == child.Name or (target and target in child.Name):
                        selected = _select_item(child)
                        break

        # 3. 收起下拉框
        if expanded:
            try:
                control.GetExpandCollapsePattern().Collapse()
            except Exception:
                pass

        if not selected:
            raise BaseException(ELEMENT_NO_FOUND, "未找到匹配的下拉框选项")

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
    def set_checked(
        pick: WinPick,
        check_type: ElementCheckedTypeFlag = ElementCheckedTypeFlag.CHECK,
        wait_time: float = 10.0,
    ):
        """设置复选框（桌面）：勾选/取消勾选/反选"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        control = WinEleCore.find(pick, wait_time).control()

        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()

        if check_type == ElementCheckedTypeFlag.TOGGLE:
            try:
                control.GetTogglePattern().Toggle()
                return
            except Exception:
                pass
        else:
            want_on = check_type == ElementCheckedTypeFlag.CHECK
            try:
                toggle_pattern = control.GetTogglePattern()
                # ToggleState: 0=Off 1=On 2=Indeterminate
                is_on = toggle_pattern.ToggleState == 1
                if is_on != want_on:
                    toggle_pattern.Toggle()
                return
            except Exception:
                pass
            try:
                item_pattern = control.GetSelectionItemPattern()
                if want_on:
                    item_pattern.Select()
                else:
                    item_pattern.RemoveFromSelection()
                return
            except Exception:
                pass

        # 兜底：点击切换
        locator = WinEleCore.find(pick, wait_time)
        point = locator.point()
        if human_sim.should_jitter_click():
            pyautogui.click(human_sim.jitter(point.x), human_sim.jitter(point.y))
        else:
            pyautogui.click(point.x, point.y)

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
    def set_value(pick: WinPick, value: str = "", wait_time: float = 10.0):
        """设置元素值（桌面）：通过UIA接口直接设置元素值，一般用于输入框和下拉框"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        control = WinEleCore.find(pick, wait_time).control()
        try:
            control.GetValuePattern().SetValue(str(value))
        except Exception:
            try:
                control.GetLegacyIAccessiblePattern().SetValue(str(value))
            except Exception:
                raise BaseException(
                    ELEMENT_NO_FOUND,
                    "该元素不支持设置值，请使用填写输入框指令",
                )

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "wait_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param("wait_time", types="Float"),
        ],
        outputList=[atomicMg.param("wait_result", types="Bool")],
    )
    def wait_element(
        pick: WinPick,
        wait_type: ElementWaitTypeFlag = ElementWaitTypeFlag.APPEAR,
        wait_time: float = 10.0,
    ) -> bool:
        """等待元素（桌面）：等待元素出现或消失，返回等待结果"""
        wait_time = max(0, float(wait_time))
        deadline = time.time() + wait_time
        while True:
            try:
                WinEleCore.find(pick=pick, wait_time=0)
                found = True
            except Exception:
                found = False
            if wait_type == ElementWaitTypeFlag.APPEAR and found:
                return True
            if wait_type == ElementWaitTypeFlag.DISAPPEAR and not found:
                return True
            if time.time() >= deadline:
                return False
            time.sleep(0.3)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "info_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression="return $this.info_type.value == '{}'".format(ElementInfoTypeFlag.ATTRIBUTE.value),
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("ele_info", types="Any")],
    )
    def get_element_info(
        pick: WinPick,
        info_type: ElementInfoTypeFlag = ElementInfoTypeFlag.TEXT,
        attribute_name: str = "",
        wait_time: float = 10.0,
    ):
        """获取元素信息（桌面）：获取元素的文本内容、值或属性"""
        locator = WinEleCore.find(pick, wait_time)
        control = locator.control()
        if info_type == ElementInfoTypeFlag.TEXT:
            return control.Name
        elif info_type == ElementInfoTypeFlag.VALUE:
            try:
                return control.GetValuePattern().Value
            except Exception:
                try:
                    return control.GetLegacyIAccessiblePattern().Value
                except Exception:
                    return ""
        else:  # ATTRIBUTE
            return _get_element_attribute(control, attribute_name, 0)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "relative_to",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
        outputList=[
            atomicMg.param("pos_left", types="Int"),
            atomicMg.param("pos_top", types="Int"),
            atomicMg.param("pos_width", types="Int"),
            atomicMg.param("pos_height", types="Int"),
            atomicMg.param("center_x", types="Int"),
            atomicMg.param("center_y", types="Int"),
        ],
    )
    def get_element_position(
        pick: WinPick,
        relative_to: PositionRelativeToFlag = PositionRelativeToFlag.SCREEN,
        wait_time: float = 10.0,
    ):
        """获取元素位置（桌面）：相对屏幕或所在窗口的位置信息"""
        locator = WinEleCore.find(pick, wait_time)
        rect = locator.rect()
        left, top = rect.left, rect.top
        if relative_to == PositionRelativeToFlag.WINDOW:
            control = locator.control()
            top_level = control.GetTopLevelControl()
            if top_level:
                window_rect = top_level.BoundingRectangle
                left -= window_rect.left
                top -= window_rect.top
        width, height = rect.width(), rect.height()
        return left, top, width, height, left + width // 2, top + height // 2

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[atomicMg.param("relative_ele", types="WinPick")],
    )
    def get_relative_element(
        pick: WinPick,
        relative_type: RelativeTypeFlag = RelativeTypeFlag.PARENT,
        wait_time: float = 10.0,
    ):
        """获取关联元素（桌面）：获取元素的父元素、第一个子元素、相邻同级元素"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        control = WinEleCore.find(pick, wait_time).control()
        if relative_type == RelativeTypeFlag.PARENT:
            target = control.GetParentControl()
        elif relative_type == RelativeTypeFlag.FIRST_CHILD:
            target = control.GetFirstChildControl()
        elif relative_type == RelativeTypeFlag.NEXT_SIBLING:
            target = control.GetNextSiblingControl()
        else:
            target = control.GetPreviousSiblingControl()

        if not target:
            raise BaseException(ELEMENT_NO_FOUND, "未找到{}元素".format(relative_type.value))

        from astronverse.locator.core.uia_locator import UIALocator

        win_pick = WinPick()
        win_pick.locator = UIALocator(control=target)
        return win_pick

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "pick_to",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                dynamics=[
                    DynamicsItem(
                        key="$this.pick_to.show",
                        expression="return $this.drag_type.value == '{}'".format(DragTypeFlag.TO_ELEMENT.value),
                    )
                ],
            ),
            atomicMg.param(
                "offset_x",
                dynamics=[
                    DynamicsItem(
                        key="$this.offset_x.show",
                        expression="return $this.drag_type.value == '{}'".format(DragTypeFlag.TO_OFFSET.value),
                    )
                ],
            ),
            atomicMg.param(
                "offset_y",
                dynamics=[
                    DynamicsItem(
                        key="$this.offset_y.show",
                        expression="return $this.drag_type.value == '{}'".format(DragTypeFlag.TO_OFFSET.value),
                    )
                ],
            ),
        ],
    )
    def drag_element(
        pick: WinPick,
        drag_type: DragTypeFlag = DragTypeFlag.TO_ELEMENT,
        pick_to: WinPick = None,
        offset_x: int = 0,
        offset_y: int = 0,
        wait_time: float = 10.0,
    ):
        """拖拽元素（桌面）：将元素拖拽至目标元素上或目标点"""
        start_point = WinEleCore.find(pick, wait_time).point()

        if drag_type == DragTypeFlag.TO_ELEMENT:
            if not pick_to:
                raise BaseException(UNPICKABLE, "未指定拖拽目标元素")
            end_point = WinEleCore.find(pick_to, wait_time).point()
        else:
            end_point = Point(start_point.x + int(offset_x), start_point.y + int(offset_y))

        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()

        pyautogui.moveTo(start_point.x, start_point.y, duration=0.2)
        pyautogui.mouseDown(button="left")
        try:
            pyautogui.moveTo(
                end_point.x,
                end_point.y,
                duration=human_sim.move_duration() if hasattr(human_sim, "move_duration") else 0.4,
            )
        finally:
            pyautogui.mouseUp(button="left")

    @staticmethod
    def _probe_element(pick: WinPick) -> bool:
        """探测单个桌面元素是否出现（不抛异常）"""
        if not pick:
            return False
        try:
            WinEleCore.find(pick=pick, wait_time=0)
            return True
        except Exception:
            return False

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_1", types="Str", required=False),
            atomicMg.param(
                "pick_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_2", types="Str", required=False),
            atomicMg.param(
                "pick_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_3", types="Str", required=False),
            atomicMg.param(
                "pick_4",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_4", types="Str", required=False),
            atomicMg.param(
                "pick_5",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_5", types="Str", required=False),
            atomicMg.param("wait_time", types="Float"),
        ],
        outputList=[
            atomicMg.param("hit_element_name", types="Str"),
            atomicMg.param("wait_result", types="Bool"),
        ],
    )
    def wait_any_element(
        pick_1: WinPick = None,
        name_1: str = "元素1",
        pick_2: WinPick = None,
        name_2: str = "元素2",
        pick_3: WinPick = None,
        name_3: str = "元素3",
        pick_4: WinPick = None,
        name_4: str = "元素4",
        pick_5: WinPick = None,
        name_5: str = "元素5",
        wait_time: float = 10.0,
    ):
        """等待任意一个元素出现（桌面）：轮询多个元素，任意一个出现即返回其名称"""
        candidates = [
            (pick_i, str(name_i))
            for pick_i, name_i in [
                (pick_1, name_1),
                (pick_2, name_2),
                (pick_3, name_3),
                (pick_4, name_4),
                (pick_5, name_5),
            ]
            if pick_i
        ]
        if not candidates:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要拾取一个元素")

        wait_time = max(0, float(wait_time))
        deadline = time.time() + wait_time
        while True:
            for pick_i, name_i in candidates:
                if WinEle._probe_element(pick_i):
                    return name_i, True
            if time.time() >= deadline:
                return "", False
            time.sleep(0.3)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param("group_a_name", types="Str", required=False),
            atomicMg.param(
                "pick_a_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_a_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_a_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("group_b_name", types="Str", required=False),
            atomicMg.param(
                "pick_b_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_b_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_b_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("wait_time", types="Float"),
        ],
        outputList=[
            atomicMg.param("hit_group_name", types="Str"),
            atomicMg.param("wait_result", types="Bool"),
        ],
    )
    def wait_any_group(
        group_a_name: str = "组A",
        pick_a_1: WinPick = None,
        pick_a_2: WinPick = None,
        pick_a_3: WinPick = None,
        group_b_name: str = "组B",
        pick_b_1: WinPick = None,
        pick_b_2: WinPick = None,
        pick_b_3: WinPick = None,
        wait_time: float = 10.0,
    ):
        """等待任意一组元素出现（桌面）：组内全部元素出现即该组命中，返回命中组名"""
        groups = []
        group_a = [p for p in [pick_a_1, pick_a_2, pick_a_3] if p]
        if group_a:
            groups.append((str(group_a_name), group_a))
        group_b = [p for p in [pick_b_1, pick_b_2, pick_b_3] if p]
        if group_b:
            groups.append((str(group_b_name), group_b))
        if not groups:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要配置一组元素")

        wait_time = max(0, float(wait_time))
        deadline = time.time() + wait_time
        while True:
            for group_name, group_picks in groups:
                if all(WinEle._probe_element(p) for p in group_picks):
                    return group_name, True
            if time.time() >= deadline:
                return "", False
            time.sleep(0.3)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_4",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "pick_5",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("picks", types="List"),
            atomicMg.param("pick_count", types="Int"),
        ],
    )
    def combine_elements(
        pick_1: WinPick = None,
        pick_2: WinPick = None,
        pick_3: WinPick = None,
        pick_4: WinPick = None,
        pick_5: WinPick = None,
    ):
        """组合多元素（桌面）：将拾取的多个元素合成一个元素列表"""
        picks = [p for p in [pick_1, pick_2, pick_3, pick_4, pick_5] if p]
        if not picks:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要拾取一个元素")
        return picks, len(picks)


# ---- P1-2 软件(win)扩展 ----

# (属性名, 是否为方法调用)
_UIA_ATTRIBUTE_SPECS = [
    ("Name", False),
    ("ClassName", False),
    ("ControlTypeName", False),
    ("LocalizedControlType", False),
    ("AutomationId", False),
    ("ProcessId", False),
    ("FrameworkId", False),
    ("IsEnabled", False),
    ("IsKeyboardFocusable", False),
    ("HasKeyboardFocus", False),
    ("IsPassword", False),
    ("IsOffscreen", True),
    ("HelpText", False),
    ("AriaRole", False),
    ("AriaProperties", False),
    ("Culture", False),
    ("NativeWindowHandle", False),
]


def _collect_uia_attributes(control) -> dict:
    """采集 uiautomation Control 的常用属性为字典"""
    attrs = {}
    for attr_name, is_method in _UIA_ATTRIBUTE_SPECS:
        try:
            value = getattr(control, attr_name, None)
            if is_method and callable(value):
                value = value()
            if value is None:
                continue
            attrs[attr_name] = str(value)
        except Exception:
            continue
    try:
        rect = control.BoundingRectangle
        attrs["BoundingRectangle"] = f"({rect.left},{rect.top},{rect.right},{rect.bottom})"
    except Exception:
        pass
    try:
        attrs["Value"] = control.GetValuePattern().Value
    except Exception:
        try:
            attrs["Value"] = control.GetLegacyIAccessiblePattern().Value
        except Exception:
            pass
    return attrs


def _collect_descendant_texts(control, max_depth: int = 20) -> list[str]:
    """递归收集元素及全部子孙的非空文本（按UI树先序顺序）"""
    texts = []
    stack = [(control, 0)]
    while stack:
        cur, depth = stack.pop()
        try:
            name = cur.Name
        except Exception:
            name = None
        if name:
            texts.append(str(name))
        if depth >= max_depth:
            continue
        try:
            children = cur.GetChildren()
        except Exception:
            children = []
        for child in reversed(children):
            stack.append((child, depth + 1))
    return texts


class WinEleExtension:
    """桌面元素扩展操作（属性/文本/批量抓取/滚动显示）"""

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[
            atomicMg.param("attributes", types="Dict"),
            atomicMg.param("attribute_count", types="Int"),
        ],
    )
    def get_all_attributes(pick: WinPick, wait_time: float = 10.0):
        """获取元素全部属性（桌面）：采集元素常用UIA属性，输出字典"""
        control = WinEleCore.find(pick, wait_time).control()
        attrs = _collect_uia_attributes(control)
        if not attrs:
            raise BaseException(ELEMENT_NO_FOUND, "未能获取到元素属性")
        return attrs, len(attrs)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[
            atomicMg.param("all_text", types="Str"),
            atomicMg.param("text_list", types="List"),
            atomicMg.param("text_count", types="Int"),
        ],
    )
    def get_all_text(
        pick: WinPick,
        separator: str = "\n",
        include_self: bool = True,
        max_depth: int = 20,
        wait_time: float = 10.0,
    ):
        """获取元素所有文本（桌面）：递归收集元素及子孙的全部文本"""
        control = WinEleCore.find(pick, wait_time).control()
        texts = _collect_descendant_texts(control, max_depth)
        if not include_self:
            try:
                self_name = str(control.Name or "")
            except Exception:
                self_name = ""
            if self_name and self_name in texts:
                texts.remove(self_name)
        joined = separator.join(texts)
        return joined, texts, len(texts)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[
            atomicMg.param("data_table", types="List"),
            atomicMg.param("row_count", types="Int"),
        ],
    )
    def batch_scrape(
        pick: WinPick,
        include_self_text: bool = False,
        max_depth: int = 10,
        wait_time: float = 10.0,
    ):
        """批量数据抓取（桌面）：按相似元素逐行抓取子孙文本，输出二维列表"""
        if pick.get("elementData", {}).get("type", None) != PickerDomain.UIA.value:
            raise BaseException(UNPICKABLE, "类型不支持{}".format(pick.get("type", None)))

        locator_list = WinEleCore.find(pick, wait_time)
        if not locator_list:
            raise BaseException(ELEMENT_NO_FOUND, "未找到相似元素")
        if not isinstance(locator_list, list):
            locator_list = [locator_list]

        rows = []
        for locator in locator_list:
            try:
                control = locator.control()
            except Exception:
                continue
            texts = _collect_descendant_texts(control, max_depth)
            if not include_self_text:
                try:
                    self_name = str(control.Name or "")
                except Exception:
                    self_name = ""
                if self_name and self_name in texts:
                    texts.remove(self_name)
            if texts:
                rows.append(texts)
        if not rows:
            raise BaseException(ELEMENT_NO_FOUND, "相似元素中未抓取到数据")
        return rows, len(rows)

    @staticmethod
    @atomicMg.atomic(
        "WinEle",
        inputList=[
            atomicMg.param(
                "pick",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[],
    )
    def scroll_into_view(
        pick: WinPick,
        auto_click: bool = False,
        max_ancestor: int = 10,
        wait_time: float = 10.0,
    ):
        """显示指定元素（桌面）：通过ScrollItemPattern将元素滚动到可视区域，可选自动点击"""
        locator = WinEleCore.find(pick, wait_time)
        control = locator.control()

        scrolled = False
        cur = control
        for _ in range(max(int(max_ancestor), 1)):
            try:
                cur.GetScrollItemPattern().ScrollIntoView()
                scrolled = True
                break
            except Exception:
                pass
            try:
                cur = cur.GetParentControl()
            except Exception:
                break
            if cur is None:
                break
        if not scrolled:
            raise BaseException(ELEMENT_NO_FOUND, "元素及其祖先均不支持滚动操作")

        if auto_click:
            point = locator.point()
            human_sim.pre_action_pause()
            locator.move(point)
            pyautogui.click(clicks=1, button="left", interval=human_sim.click_interval())
