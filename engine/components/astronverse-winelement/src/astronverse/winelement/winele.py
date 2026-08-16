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
