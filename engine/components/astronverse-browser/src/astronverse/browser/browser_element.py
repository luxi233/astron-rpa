import base64
import json
import os
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, AtomicLevel, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.humansim import human_sim
from astronverse.actionlib.types import PATH, WebPick
from astronverse.baseline.logger.logger import logger
from astronverse.browser import *
from astronverse.browser.browser import Browser
from astronverse.browser.browser_script import eval_js_code
from astronverse.browser.core.core_win import BrowserCore
from astronverse.browser.error import *
from astronverse.browser.utils.table_filter import (
    DataFilter,
    page_values_merge,
    table_df_to_out,
    table_json_merge_values,
)
from astronverse.locator import smooth_move
from astronverse.locator.locator import locator


def get_browser_instance():
    return get_default_browser()


def get_default_browser(raw_browser_type: str = None):
    """获取可用的浏览器实例。"""
    control = None
    browser_type = CommonForBrowserType.BTChrome
    for bt in ALL_BROWSER_TYPES:
        if raw_browser_type and bt.value != raw_browser_type:
            continue
        control = BrowserCore.get_browser_control(bt.value)
        if control:
            browser_type = bt
            break
    if not control:
        return None
    browser = Browser()
    browser.browser_control = control
    browser.browser_type = browser_type
    return browser


def check_element(browser_obj: Browser, element_data: WebPick, element_timeout: int = 10):
    """检测browser_obj， element_data"""
    if element_data:
        if element_data.get("elementData", {}).get("app", "") == "iexplore":
            raise Exception(
                "拾取元素类型需要跟浏览器类型保持一致！当前操作的浏览器为！{}".format(browser_obj.browser_type.value)
            )

    if not browser_obj:
        browser_obj = get_default_browser()

    if element_data:
        res = BrowserElement.wait_element(
            browser_obj=browser_obj,
            element_data=element_data,
            ele_status=WaitElementForStatusFlag.ElementExists,
            element_timeout=element_timeout,
        )
        if not res:
            reason = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="checkElement",
                data=element_data["elementData"]["path"],
            )
            msg = ""
            if isinstance(reason, dict):
                msg = reason.get("msg", "")
            raise BaseException(WEB_GET_ELE_ERROR.format(msg), "浏览器元素未找到！")
    return browser_obj


class BrowserElement:
    """浏览器元素操作类，提供网页元素的各种操作方法。"""

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        outputList=[
            atomicMg.param("wait_element", types="Bool"),
        ],
    )
    def wait_element(
        browser_obj: Browser,
        element_data: WebPick,
        ele_status: WaitElementForStatusFlag = WaitElementForStatusFlag.ElementExists,
        element_timeout: int = 10,
    ) -> bool:
        """等待元素出现或消失。"""
        if element_data:
            if element_data.get("elementData", {}).get("app", "") == "iexplore":
                raise Exception(
                    "拾取元素类型需要跟浏览器类型保持一致！当前操作的浏览器为！{}".format(
                        browser_obj.browser_type.value
                    )
                )

        if not browser_obj:
            browser_obj = get_default_browser()

        timeout = element_timeout
        if timeout < 0:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(timeout), f"等待时间不能小于0！{timeout}")
        while timeout >= 0:
            start = time.time()
            # 获取状态
            try:
                element_exist = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="elementIsReady",
                    data=element_data["elementData"]["path"],
                )
            except Exception:
                element_exist = None

            # 判断是否提前结束
            if (
                ele_status == WaitElementForStatusFlag.ElementExists
                and element_exist
                or ele_status == WaitElementForStatusFlag.ElementDisappears
                and not element_exist
            ):
                return True
            else:
                # 重试
                time.sleep(0.3)
                use = time.time() - start
                timeout -= use
        return False

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("simulate_flag", required=False),
            atomicMg.param(
                "assistive_key",
                dynamics=[
                    DynamicsItem(
                        key="$this.assistive_key.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "button_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "scroll_into_center",
                level=AtomicLevel.ADVANCED,
                dynamics=[
                    DynamicsItem(
                        key="$this.scroll_into_center.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
                required=False,
            ),
        ],
    )
    def click(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        simulate_flag: bool = False,
        assistive_key: ButtonForAssistiveKeyFlag = ButtonForAssistiveKeyFlag.Nothing,
        button_type: ButtonForClickTypeFlag = ButtonForClickTypeFlag.Left,
        element_timeout: int = 10,
        scroll_into_center: bool = True,
    ):
        """点击"""
        try:
            browser_obj = check_element(browser_obj, element_data, element_timeout)

            # 模拟真人：操作前随机停顿
            human_sim.pre_action_pause()

            if assistive_key != ButtonForAssistiveKeyFlag.Nothing:
                from astronverse.input.code.keyboard import Keyboard

                Keyboard.key_down(assistive_key.value)

            if not simulate_flag:
                # js点击
                browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="clickElement",
                    data={
                        **element_data["elementData"]["path"],  # 解包内部字典的内容
                        "atomConfig": {"buttonType": button_type.value},
                    },
                )
            else:
                # 定位
                element = locator.locator(
                    element_data.get("elementData"),
                    cur_target_app=browser_obj.browser_type.value,
                    scroll_into_center=scroll_into_center,
                )
                if isinstance(element.rect(), list):
                    raise Exception("浏览器元素定位不唯一，请检查！")

                # 点击
                center = element.point()
                smooth_move(center.x, center.y, duration=0.5)
                from astronverse.input.code.mouse import Mouse

                Mouse.click(
                    x=center.x,
                    y=center.y,
                    clicks=2 if button_type == ButtonForClickTypeFlag.Double else 1,
                    button=("left" if button_type != ButtonForClickTypeFlag.Right else "right"),
                )
        finally:
            if assistive_key != ButtonForAssistiveKeyFlag.Nothing:
                from astronverse.input.code.keyboard import Keyboard

                Keyboard.key_up(assistive_key.value)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("simulate_flag", required=False),
            atomicMg.param(
                "focus_time",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.focus_time.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "fill_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "write_gap_time",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.write_gap_time.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "fill_input",
                dynamics=[
                    DynamicsItem(
                        key="$this.fill_input.show",
                        expression=f"return $this.fill_type.value == '{FillInputForFillTypeFlag.Text.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "fill_input_credential",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value, params={"filters": ["credential"]}),
                dynamics=[
                    DynamicsItem(
                        key="$this.fill_input_credential.show",
                        expression=f"return $this.fill_type.value == '{FillInputForFillTypeFlag.Credential.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "input_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "scroll_into_center",
                level=AtomicLevel.ADVANCED,
                dynamics=[
                    DynamicsItem(
                        key="$this.scroll_into_center.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("form_input", types="Str"),
        ],
    )
    def input(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        simulate_flag: bool = False,
        fill_type: FillInputForFillTypeFlag = FillInputForFillTypeFlag.Text,
        fill_input: str = "",
        fill_input_credential: str = "",
        element_timeout: int = 10,
        focus_time: float = 1000,
        write_gap_time: float = 0,
        input_type: FillInputForInputTypeFlag = FillInputForInputTypeFlag.Overwrite,
        scroll_into_center: bool = True,
    ):
        """
        填写输入框(web)
        """
        browser_obj = check_element(browser_obj, element_data, element_timeout)

        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()

        if fill_type == FillInputForFillTypeFlag.Text:
            text = fill_input
        elif fill_type == FillInputForFillTypeFlag.Clipboard:
            from astronverse.input.code.clipboard import Clipboard

            text = Clipboard.paste()
        elif fill_type == FillInputForFillTypeFlag.Credential:
            from astronverse.actionlib.utils import Credential

            text = Credential.get_credential(fill_input_credential)
        else:
            text = ""

        # js输入
        if not simulate_flag:
            # 获取原始数据
            if input_type == FillInputForInputTypeFlag.Append:
                origin_text = BrowserElement.element_text(
                    browser_obj=browser_obj,
                    element_data=element_data,
                    element_timeout=10,
                )
                if origin_text:
                    text = str(origin_text) + str(text)

            # 输入
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="inputElement",
                data={
                    **element_data["elementData"]["path"],  # 解包内部字典的内容
                    "atomConfig": {"inputText": text},
                },
            )
        else:
            from astronverse.input.code.keyboard import Keyboard
            from astronverse.input.code.mouse import Mouse

            # 参数验证
            if focus_time < 0:
                raise BaseException(FOCUS_TIMEOUT_MUST_BE_POSITIVE, "焦点超时时间必须大于0")
            if write_gap_time < 0:
                raise BaseException(KEY_PRESS_INTERVAL_MUST_BE_NON_NEGATIVE, "按键输入间隔必须大于等于0")

            # 定位
            element = locator.locator(
                element_data.get("elementData"),
                cur_target_app=browser_obj.browser_type.value,
                scroll_into_center=scroll_into_center,
            )
            if isinstance(element.rect(), list):
                raise Exception("浏览器元素定位不唯一，请检查！")

            # 点击
            center = element.point()
            smooth_move(center.x, center.y, duration=0.4)
            Mouse.click(x=center.x, y=center.y)

            # 清空输入
            if input_type == FillInputForInputTypeFlag.Overwrite:
                Keyboard.hotkey("ctrl", "a")
                time.sleep(0.5)
                Keyboard.press("delete")
                time.sleep(0.5)

            # 聚焦时间
            time.sleep(focus_time / 1000)

            # 填充类型
            if fill_type == FillInputForFillTypeFlag.Text:
                for item in text:
                    Keyboard.write_unicode(item)
                    # 输入间隔时间
                    time.sleep(write_gap_time if write_gap_time > 0 else 0.03)
            elif fill_type == FillInputForFillTypeFlag.Clipboard:
                from astronverse.input.code.clipboard import Clipboard

                Clipboard.copy(data=text)
                Keyboard.hotkey("ctrl", "v")

        return text

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("scroll_into_center", level=AtomicLevel.ADVANCED, required=False),
        ],
        outputList=[],
    )
    def hover_over(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        element_timeout: int = 10,
        scroll_into_center: bool = True,
    ):
        """
        鼠标悬停在元素上（web）
        """
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        # 模拟真人：操作前随机停顿
        human_sim.pre_action_pause()
        element = locator.locator(
            element_data.get("elementData"),
            cur_target_app=browser_obj.browser_type.value,
            scroll_into_center=scroll_into_center,
        )
        if isinstance(element.rect(), list):
            raise Exception("浏览器元素定位不唯一，请检查！")
        element.move()

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "file_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "folder"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("xpath_shot", types="Str"),
        ],
    )
    def screenshot(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        file_path: PATH = None,
        image_name: str = "",
        element_timeout: int = 10,
    ):
        """截图"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="elementShot",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
            },
            timeout=30,
        )
        if data:
            data = data.replace("data:image/jpeg;base64,", "")
        else:
            raise Exception("插件返回数据为空")

        # 输出
        if not image_name.endswith((".png", ".jpg", ".jpeg")):
            image_name += ".jpg"
        path = os.path.join(file_path, image_name)
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "file_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "folder"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("position_shot", types="Str"),
        ],
    )
    def position_screenshot(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        file_path: PATH = None,
        image_name: str = "",
        element_timeout: int = 10,
    ):
        """元素位置截图"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        element = locator.locator(element_data.get("elementData"), cur_target_app=browser_obj.browser_type.value)
        if isinstance(element.rect(), list):
            raise Exception("浏览器元素定位不唯一，请检查！")
        rect = element.rect()

        if not image_name.endswith((".png", ".jpg", ".jpeg")):
            image_name += ".jpg"
        path = os.path.join(file_path, image_name)
        from astronverse.input.code.screenshot import Screenshot

        Screenshot.screenshot(region=(rect.left, rect.top, rect.width(), rect.height()), file_path=path)
        return path

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "scrollbar_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "element_data",
                dynamics=[
                    DynamicsItem(
                        key="$this.element_data.show",
                        expression=f"return $this.scrollbar_type.value == '{ScrollbarType.CustomEle.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "element_timeout",
                dynamics=[
                    DynamicsItem(
                        key="$this.element_timeout.show",
                        expression=f"return $this.scrollbar_type.value == '{ScrollbarType.CustomEle.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "x_scroll_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.x_scroll_type.show",
                        expression=f"return $this.scroll_direction.value == '{ScrollDirection.Horizontal.value}'",
                    )
                ],
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "y_scroll_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.y_scroll_type.show",
                        expression=f"return $this.scroll_direction.value == '{ScrollDirection.Vertical.value}'",
                    )
                ],
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param(
                "x_custom_scroll_dis",
                dynamics=[
                    DynamicsItem(
                        key="$this.x_custom_scroll_dis.show",
                        expression=f"return $this.scroll_direction.value == '{ScrollDirection.Horizontal.value}' && $this.x_scroll_type.value == '{ScrollbarForXScrollTypeFlag.Defined.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "y_custom_scroll_dis",
                dynamics=[
                    DynamicsItem(
                        key="$this.y_custom_scroll_dis.show",
                        expression=f"return $this.scroll_direction.value == '{ScrollDirection.Vertical.value}' && $this.y_scroll_type.value == '{ScrollbarForYScrollTypeFlag.Defined.value}'",
                    )
                ],
            ),
        ],
    )
    def scroll(
        browser_obj: Browser = None,
        scrollbar_type: ScrollbarType = ScrollbarType.Window,
        element_data: WebPick = None,
        scroll_direction: ScrollDirection = ScrollDirection.Horizontal,
        x_scroll_type: ScrollbarForXScrollTypeFlag = ScrollbarForXScrollTypeFlag.Left,
        x_custom_scroll_dis: int = 0,
        y_scroll_type: ScrollbarForYScrollTypeFlag = ScrollbarForYScrollTypeFlag.Top,
        y_custom_scroll_dis: int = 0,
        element_timeout: int = 10,
    ):
        """滚动操作。"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)

        scroll_distance_x = ""
        scroll_distance_y = ""
        scroll_to = "top"
        scroll_axis = "y"
        if scroll_direction == ScrollDirection.Vertical:
            if y_scroll_type == ScrollbarForYScrollTypeFlag.Defined:
                scroll_distance_y = y_custom_scroll_dis
                scroll_to = "custom"
            elif y_scroll_type == ScrollbarForYScrollTypeFlag.Bottom:
                scroll_distance_y = 99999
                scroll_to = "bottom"
        else:
            scroll_to = "left"
            scroll_axis = "x"
            if x_scroll_type == ScrollbarForXScrollTypeFlag.Defined:
                scroll_distance_x = x_custom_scroll_dis
                scroll_to = "custom"
            elif x_scroll_type == ScrollbarForXScrollTypeFlag.Right:
                scroll_distance_x = 99999
                scroll_to = "right"

        if scrollbar_type == ScrollbarType.Window:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="scrollWindow",
                data={
                    "atomConfig": {
                        "scrollX": scroll_distance_x,
                        "scrollY": scroll_distance_y,
                        "scrollBehavior": "auto",
                        "scrollTo": scroll_to,
                        "scrollAxis": scroll_axis,
                    }
                },
            )
        else:
            # 自定义滚动条
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="scrollWindow",
                data={
                    **element_data["elementData"]["path"],  # 解包内部字典的内容
                    "atomConfig": {
                        "scrollX": scroll_distance_x,
                        "scrollY": scroll_distance_y,
                        "scrollBehavior": "auto",
                        "scrollTo": scroll_to,
                        "scrollAxis": scroll_axis,
                    },
                },
            )

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("scroll_into_center", level=AtomicLevel.ADVANCED, required=False),
        ],
        outputList=[],
    )
    def scroll_into_view(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        element_timeout: int = 10,
        scroll_into_center: bool = True,
    ):
        """滚动到元素可见位置。"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="scrollIntoView",
            data={**element_data["elementData"]["path"], "atomConfig": {"scrollIntoCenter": scroll_into_center}},
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeHasSelfTypeFlag.GetAttribute.value}'",
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
        browser_obj: Browser,
        element_data: WebPick,
        get_type: ElementGetAttributeHasSelfTypeFlag = ElementGetAttributeHasSelfTypeFlag.GetElement,
        attribute_name: str = "",
        element_timeout: int = 10,
    ):
        """
        获取相似元素列表
        """
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        # 获取相似元素的信息
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="elementFromSelect",
            data=element_data["elementData"]["path"],
        )
        # 遍历相似元素，将结果放入list
        if get_type == ElementGetAttributeHasSelfTypeFlag.GetElement:
            res_list = []
            for di in data:
                res_list.append(
                    {
                        "elementData": {
                            "version": element_data["elementData"]["version"],
                            "type": element_data["elementData"]["type"],
                            "app": element_data["elementData"]["app"],
                            "picker_type": "ELEMENT",
                            "path": di,
                        }
                    }
                )
            return res_list, len(res_list)

        res_list = []
        for di in data:
            data = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="getElementAttrs",
                data={
                    **di,  # 解包内部字典的内容
                    "atomConfig": {
                        "operation": str(list(ElementGetAttributeHasSelfTypeFlag).index(get_type) - 1),
                        "attrName": attribute_name,
                    },
                },
            )
            res_list.append(data)
        return res_list, len(res_list)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        noAdvanced=True,
        inputList=[
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeHasSelfTypeFlag.GetAttribute.value}'",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("index", types="Int"),
            atomicMg.param("item", types="Any"),
        ],
    )
    def loop_similar(
        browser_obj: Browser,
        element_data: WebPick,
        get_type: ElementGetAttributeHasSelfTypeFlag = ElementGetAttributeHasSelfTypeFlag.GetElement,
        start: int = 0,
        end: int = -1,
        attribute_name: str = "",
        element_timeout: int = 10,
    ):
        """循环相似元素"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)

        def get_iterator():
            count = 0
            batch_size = 20
            while True:
                data = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="getSimilarIterator",
                    data={
                        **element_data["elementData"]["path"],  # 解包内部字典的内容
                        "index": count,
                        "count": batch_size,
                    },
                )
                if not data or len(data) <= 0:
                    break
                for di in data:
                    if count < start:
                        count += 1
                        continue
                    if 0 < end <= count:
                        return
                    count += 1
                    if get_type == ElementGetAttributeHasSelfTypeFlag.GetElement:
                        di_wrapper = {
                            "elementData": {
                                "version": element_data["elementData"]["version"],
                                "type": element_data["elementData"]["type"],
                                "app": element_data["elementData"]["app"],
                                "picker_type": "ELEMENT",
                                "path": di,
                            }
                        }
                        yield count, di_wrapper
                    else:
                        res = browser_obj.send_browser_extension(
                            browser_type=browser_obj.browser_type.value,
                            key="getElementAttrs",
                            data={
                                **di,  # 解包内部字典的内容
                                "atomConfig": {
                                    "operation": str(list(ElementGetAttributeHasSelfTypeFlag).index(get_type) - 1),
                                    "attrName": attribute_name,
                                },
                            },
                        )
                        yield count, res
                similar_count = data[0]["similarCount"]
                if similar_count <= count:
                    break

        return get_iterator()

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        outputList=[
            atomicMg.param("data_pick", types="Str"),
        ],
    )
    def element_text(browser_obj: Browser, element_data: WebPick, element_timeout: int = 10) -> str:
        """
        获取元素文本内容
        """

        browser_obj = check_element(browser_obj, element_data, element_timeout)
        res = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getElementText",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
            },
        )
        return res

    @staticmethod
    @atomicMg.atomic("BrowserElement")
    def slider_hover(
        browser_obj: Browser = None,
        element_slider: WebPick = None,
        element_progress: WebPick = None,
        percent_value: float = 0.0,
        drag_direction: ElementDragDirectionTypeFlag = ElementDragDirectionTypeFlag.Left,
        drag_type: ElementDragTypeFlag = ElementDragTypeFlag.Start,
        duration: float = 0.25,
    ):
        """滑块"""
        from astronverse.input.code.mouse import Mouse

        def html_drag(start_pos, end_pos, duration):
            """
            指定起始坐标以及结束坐标进行拖拽操作
            """
            smooth_move(start_pos[0], start_pos[1], duration=0.05)
            Mouse.down(x=start_pos[0], y=start_pos[1], button="left")
            logger.info(f"slider_hover start {start_pos}  end {end_pos}")
            smooth_move(end_pos[0], end_pos[1], duration=duration)
            time.sleep(0.05)
            Mouse.up(x=end_pos[0], y=end_pos[1], button="left")  # 在结束位置释放鼠标按钮
            time.sleep(0.05)

        percent_value = max(0.0, min(1.0, percent_value / 100))
        # 定位滑块和滑条元素
        # 滑块（要拖动的元素）
        element = locator.locator(element_slider.get("elementData"), cur_target_app=browser_obj.browser_type.value)
        if isinstance(element.rect(), list):
            raise Exception("滑块元素定位不唯一，请检查！")
        slider_center = element.point()

        # 滑条（滑块可移动的轨道）
        element = locator.locator(
            element_progress.get("elementData"), cur_target_app=browser_obj.browser_type.value, scroll_into_view=False
        )
        if isinstance(element.rect(), list):
            raise Exception("滑轨元素定位不唯一，请检查！")
        progress_rect = element.rect()

        # 计算滑条的尺寸和位置
        progress_left = progress_rect.left
        progress_top = progress_rect.top
        progress_width = progress_rect.right - progress_rect.left
        progress_height = progress_rect.bottom - progress_rect.top

        # 记录滑块初始位置
        start_pos = [slider_center.x, slider_center.y]
        logger.info(f"滑块中心点: {start_pos}")
        logger.info(f"滑条位置和尺寸: [{progress_left}, {progress_top}, {progress_width}, {progress_height}]")

        # 根据拖拽方向判断是横向还是纵向
        is_horizontal = drag_direction in [
            ElementDragDirectionTypeFlag.Left,
            ElementDragDirectionTypeFlag.Right,
        ]
        logger.info(f"滑动方向: {'横向' if is_horizontal else '纵向'}, 具体方向: {drag_direction.value}")

        # 计算终点位置
        if is_horizontal:
            # 横向滑块
            if drag_type == ElementDragTypeFlag.Start:  # 从起点模式
                if drag_direction == ElementDragDirectionTypeFlag.Right:
                    # 向右滑动，直接使用百分比
                    target_x = progress_left + (progress_width * percent_value)
                else:  # 向左滑动
                    # 使用反向百分比（1-percent_value）
                    target_x = progress_left + (progress_width * (1 - percent_value))
                end_pos = [int(target_x), int(slider_center.y)]
            else:  # 相对当前位置模式
                # 计算移动距离
                move_distance = progress_width * percent_value
                if drag_direction == ElementDragDirectionTypeFlag.Left:
                    move_distance = -move_distance
                # 计算目标位置
                target_x = slider_center.x + move_distance
                # 确保不超出滑条范围
                target_x = max(progress_left, min(progress_left + progress_width, target_x))
                end_pos = [int(target_x), int(slider_center.y)]
        else:
            # 纵向滑块
            if drag_type == ElementDragTypeFlag.Start:  # 从起点模式
                if drag_direction == ElementDragDirectionTypeFlag.Down:
                    # 向下滑动，直接使用百分比
                    target_y = progress_top + (progress_height * percent_value)
                else:  # 向上滑动
                    # 使用反向百分比（1-percent_value）
                    target_y = progress_top + (progress_height * (1 - percent_value))
                end_pos = [int(slider_center.x), int(target_y)]
            else:  # 相对当前位置模式
                # 计算移动距离
                move_distance = progress_height * percent_value
                if drag_direction == ElementDragDirectionTypeFlag.Up:
                    move_distance = -move_distance
                # 计算目标位置
                target_y = slider_center.y + move_distance
                # 确保不超出滑条范围
                target_y = max(progress_top, min(progress_top + progress_height, target_y))
                end_pos = [int(slider_center.x), int(target_y)]

        logger.info(f"计算的终点位置: {end_pos}")
        html_drag(start_pos, end_pos, duration)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[atomicMg.param("current_content", required=False)],
        outputList=[
            atomicMg.param("get_selected", types="List"),
        ],
    )
    def get_select(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        current_content: bool = True,
        element_timeout: int = 10,
    ):
        """获取下拉框选中值。"""

        browser_obj = check_element(browser_obj, element_data, element_timeout)
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getElementSelected",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
                "atomConfig": {
                    "option": "selected" if current_content else "_",
                },
            },
        )
        return data

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        outputList=[
            atomicMg.param("get_checkbox_checked", types="Str"),
        ],
    )
    def get_checked(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        element_timeout: int = 10,
    ):
        """获取复选框选中状态。"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getElementChecked",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
            },
        )
        return data

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "value",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.value.show",
                        expression=f"return ['{SelectionPartner.Contains.value}', '{SelectionPartner.Equal.value}'].includes($this.pattern.value)",
                    )
                ],
            ),
            atomicMg.param(
                "solution",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.solution.show",
                        expression=f"return $this.pattern.value == '{SelectionPartner.Index.value}'",
                    )
                ],
            ),
        ],
    )
    def set_select(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        pattern: SelectionPartner = SelectionPartner.Contains,
        value: str = "",
        solution: int = 0,
        element_timeout: int = 10,
    ):
        """设置下拉框选中值。"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="setElementSelected",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
                "atomConfig": {
                    "value": value,
                    "pattern": pattern.value,
                    "indexValue": solution,
                },
            },
        )

    @staticmethod
    @atomicMg.atomic("BrowserElement")
    def set_checked(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        checked_type: ElementCheckedTypeFlag = ElementCheckedTypeFlag.Checked,
        element_timeout: int = 10,
    ):
        """设置复选框选中状态。"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="setElementChecked",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
                "atomConfig": {
                    "checked": checked_type == ElementCheckedTypeFlag.Checked,
                    "reverse": checked_type == ElementCheckedTypeFlag.Reversed,
                },
            },
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "get_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_type.show",
                        expression=f"return $this.operation_type.value == '{ElementAttributeOpTypeFlag.Get.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "attribute_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_name.show",
                        expression="return ['getAttribute','getStyle'].includes($this.get_type.value) || ['set', 'del'].includes($this.operation_type.value)",
                    )
                ],
            ),
            atomicMg.param(
                "position",
                dynamics=[
                    DynamicsItem(
                        key="$this.position.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetPosition.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "attribute_value",
                dynamics=[
                    DynamicsItem(
                        key="$this.attribute_value.show",
                        expression=f"return $this.operation_type.value == '{ElementAttributeOpTypeFlag.Set.value}'",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param(
                "get_ele_attr",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_attr.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetAttribute.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_value",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_value.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetValue.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_html",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_html.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetHtml.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_link",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_link.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetLink.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_text",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_text.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetText.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_position",
                types="List",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_position.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetPosition.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_selected",
                types="Bool",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_selected.show",
                        expression=f"return $this.get_type.value == '{ElementGetAttributeTypeFlag.GetSelection.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "get_ele_style",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.get_ele_style.show",
                        expression="return $this.get_type.value == '{}'".format(
                            ElementGetAttributeTypeFlag.GetStyle.value
                        ),
                    )
                ],
            ),
        ],
    )
    def element_operation(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        operation_type: ElementAttributeOpTypeFlag = ElementAttributeOpTypeFlag.Get,
        get_type: ElementGetAttributeTypeFlag = ElementGetAttributeTypeFlag.GetText,
        attribute_name: str = "",
        position: RelativePosition = RelativePosition.ScreenLeft,
        attribute_value: str = "",
        element_timeout: int = 10,
    ):
        """三个操作大类是候选，其他参数是候选出现后出现"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        if operation_type == ElementAttributeOpTypeFlag.Del:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="removeElementAttr",
                data={
                    **element_data["elementData"]["path"],  # 解包内部字典的内容
                    "atomConfig": {
                        "attrName": attribute_name,
                    },
                },
            )
        elif operation_type == ElementAttributeOpTypeFlag.Get:
            data = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="getElementAttrs",
                data={
                    **element_data["elementData"]["path"],  # 解包内部字典的内容
                    "atomConfig": {
                        "attrName": attribute_name,
                        "operation": str(list(ElementGetAttributeTypeFlag).index(get_type)),
                    },
                },
            )

            logger.info(f"获取元素属性: {data}")
            if get_type == ElementGetAttributeTypeFlag.GetPosition:
                if position == RelativePosition.ScreenLeft:
                    top, left = BrowserCore.get_browser_point(browser_obj.browser_type.value)
                    return [
                        data["x"] + left,
                        data["y"] + top,
                        data["right"] + left,
                        data["bottom"] + top,
                    ]
                # 返回的是列表
                return [data["x"], data["y"], data["right"], data["bottom"]]
            else:
                return data

        elif operation_type == ElementAttributeOpTypeFlag.Set:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="setElementAttr",
                data={
                    **element_data["elementData"]["path"],  # 解包内部字典的内容
                    "atomConfig": {
                        "attrName": attribute_name,
                        "attrValue": attribute_value,
                    },
                },
            )

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "excel_path",
                dynamics=[
                    DynamicsItem(
                        key="$this.excel_path.show",
                        expression="return $this.to_excel.value == true",
                    )
                ],
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "file"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("table_pick", types="List"),
        ],
    )
    def get_table(
        browser_obj: Browser,
        element_data: WebPick,
        to_excel: bool = False,  # 是否导出excel
        excel_path: str = "",  # excel路径
        element_timeout: int = 10,
    ):
        """
        获取表格内容
        """
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        table_data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getTableData",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
            },
        )

        # 判断table_data 存在 tbody
        if "tbody" in table_data:
            import pandas as pd

            df = pd.DataFrame(table_data["tbody"])
            table_body = df.values.tolist()
            # 添加表头
            table_head = table_data["thead"]
            df.columns = table_data["thead"]
            table_list = table_body
            if to_excel:
                # 检查 excel_path 是否为 .xlsx 文件
                if excel_path and not excel_path.endswith(".xlsx"):
                    raise Exception(f"{excel_path}表格文件路径错误，仅支持 .xlsx 文件")
                if excel_path is None:
                    excel_path = f"{element_data['elementData']['name']}.xlsx"
                df.to_excel(excel_path, index=False)
            return [table_head] + table_list
        else:
            raise Exception(table_data["msg"])

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "batch_data",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "BATCH"}),
            ),
            # multi_page  为 True 时，page_element_data，page_count，page_interval参数必须存在
            atomicMg.param("multi_page", required=False),
            atomicMg.param(
                "page_count",
                dynamics=[
                    DynamicsItem(
                        key="$this.page_count.show",
                        expression="return $this.multi_page.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "page_interval",
                dynamics=[
                    DynamicsItem(
                        key="$this.page_interval.show",
                        expression="return $this.multi_page.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "element_data",
                dynamics=[
                    DynamicsItem(
                        key="$this.element_data.show",
                        expression="return $this.multi_page.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "simulate_flag",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.simulate_flag.show",
                        expression="return $this.multi_page.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "button_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            # to_excel 为 True 时，excel_path参数必须存在
            atomicMg.param(
                "excel_path",
                dynamics=[
                    DynamicsItem(
                        key="$this.excel_path.show",
                        expression="return $this.to_excel.value == true",
                    )
                ],
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={
                        "file_type": "file",
                        "filters": [".xlsx"],  # 在file_type为file有效 标识只要.txt的后缀文件
                        "defaultPath": "default.xlsx",  # 默认名称 只适用于 file
                    },
                ),
            ),
            atomicMg.param(
                "output_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            # 是否输出表头
            atomicMg.param("output_head", required=False),
            atomicMg.param(
                "scroll_into_center",
                level=AtomicLevel.ADVANCED,
                dynamics=[
                    DynamicsItem(
                        key="$this.scroll_into_center.show",
                        expression="return $this.simulate_flag.value == true",
                    )
                ],
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("table_pick", types="List"),
            atomicMg.param(
                "table_path",
                dynamics=[
                    DynamicsItem(
                        key="$this.table_path.show",
                        expression="return $this.to_excel.value == true",
                    )
                ],
                types="Str",
            ),
        ],
    )
    def data_batch(
        browser_obj: Browser = None,  # 浏览器对象
        batch_data: WebPick = None,  # 批量抓取对象
        multi_page: bool = False,  # 是否翻页
        page_count: int = 1,  # 翻页次数
        page_interval: int = 1,  # 翻页间隔
        element_data: WebPick = None,  # 翻页按钮元素
        simulate_flag: bool = False,  # 翻页按钮元素模拟人工点击
        button_type: ButtonForClickTypeFlag = ButtonForClickTypeFlag.Left,
        to_excel: bool = False,  # 是否导出excel
        excel_path: str = "",  # excel路径
        element_timeout: int = 10,
        output_type: TablePickType = TablePickType.Row,
        output_head: bool = True,  # 是否输出表头
        output_filter_empty_col: bool = False,  # 是否过滤空列
        is_save_to_data_table: bool = False,  # 是否保存到数据表格
        scroll_into_center: bool = True,
    ):
        """数据抓取（web）"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)

        table_list = []
        batch_element = batch_data.get("elementData")  # 抓取对象
        table_element = batch_element["path"]  # 元素信息
        produce_type = table_element["produceType"]  # 抓取类型， produceType: table/similar
        for i in range(1, page_count + 1):
            # 获取表格内容, 二维数组
            if produce_type == "table":
                # 等待元素
                wait = BrowserElement.wait_element(
                    browser_obj=browser_obj,
                    element_data=batch_data,
                    ele_status=WaitElementForStatusFlag.ElementExists,
                    element_timeout=int(element_timeout),
                )
                if not wait:
                    raise BaseException(WEB_GET_ELE_ERROR.format("请检查抓取元素"), "浏览器元素未找到！")
                # 发送给插件
                response = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="tableDataBatch",
                    data=table_element,
                )
                # 打印 response
                # logger.info(f'table_element response: {response}')
                table_values = response["values"]
                table_list = page_values_merge(table_list, table_values, produce_type)
            else:
                # 相似元素对象
                similar_element = batch_element["path"]
                wait = BrowserElement.wait_element(
                    browser_obj=browser_obj,
                    element_data={
                        "elementData": {
                            "version": batch_element["version"],
                            "type": batch_element["type"],
                            "app": batch_element["app"],
                            "picker_type": "ELEMENT",
                            "path": similar_element,
                        }
                    },
                    ele_status=WaitElementForStatusFlag.ElementExists,
                    element_timeout=int(element_timeout),
                )
                if not wait:
                    raise BaseException(WEB_GET_ELE_ERROR.format("请检查抓取元素"), "浏览器元素未找到！")
                response = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="simalarListBatch",
                    data=similar_element,
                )
                # 打印 response
                # logger.info(f'similar_element response: {response}')
                similar_values = response["values"]
                table_list = page_values_merge(table_list, similar_values, produce_type)

            # 是否翻页
            if page_count > 1 and multi_page:
                # logger.info(f'翻页: {i} 页')
                # 点击翻页按钮元素,调用 上面的click 方法
                try:
                    BrowserElement.click(
                        browser_obj=browser_obj,
                        element_data=element_data,
                        simulate_flag=simulate_flag,
                        assistive_key=ButtonForAssistiveKeyFlag.Nothing,
                        button_type=button_type,
                        element_timeout=element_timeout,
                        scroll_into_center=scroll_into_center,
                    )
                except Exception:
                    pass
                # 等待 page_interval 秒
                time.sleep(page_interval)

        # logger.info(f'表格数据: {table_list}')
        # 合并获取到的数据 到 table_element的 values 中
        data_formated = table_json_merge_values(data_json=table_element, values=table_list)
        # logger.info(f'表格数据格式化: {data_formated}')

        # 数据处理
        data_filtered = DataFilter(data_json=data_formated).get_filtered_data()
        # logger.info(f'表格数据过滤: {data_filtered}')

        # 得到过滤后的 table_df
        table_df_out = table_df_to_out(data_json=data_filtered)

        # 是否过滤空列
        if output_filter_empty_col:
            table_df_out = table_df_out.dropna(axis=1, how="all")

        output_data = []
        if output_head:
            output_data = [table_df_out.columns.tolist()] + table_df_out.values.tolist()
        else:
            output_data = table_df_out.values.tolist()

        if is_save_to_data_table:
            # 保存到数据表格
            from astronverse.datatable import WriteMode, WriteType
            from astronverse.datatable.datatable import DataTable

            DataTable.write_data(
                write_type=WriteType.AREA,
                start_row=1,
                start_col="A",
                data=output_data,
                write_mode=WriteMode.OVERWRITE,
            )

        if to_excel:
            # 将table_list 转换为excel
            # 检查 excel_path 是否为 .xlsx 文件
            if excel_path and not excel_path.endswith(".xlsx"):
                raise Exception(f"{excel_path}表格文件路径错误，仅支持 .xlsx 文件")
            if excel_path is None:
                excel_path = f"{table_element['name']}.xlsx"
            table_df_out.to_excel(excel_path, index=False, header=output_head)
            # logger.info(f'表格数据已保存到 {excel_path}')
            table_path = excel_path
            if output_type == TablePickType.Row:
                return output_data, table_path
            return table_df_out.to_dict(orient="list"), table_path

        # 返回表格数据 按行/列 返回
        if output_type == TablePickType.Row:
            return output_data
        else:
            return table_df_out.to_dict(orient="list")

    # 根据xpath/cssSelector 生成元素对象
    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[atomicMg.param("locate_type", formType=AtomicFormTypeMeta(AtomicFormType.SELECT.value))],
        outputList=[atomicMg.param("element_obj", types="Any")],
    )
    def create_element(
        browser_obj: Browser = None,  # 浏览器对象
        locate_type: LocateType = LocateType.Xpath,  # 定位方式 xpath / cssSelector / text
        locate_value: str = "",
        return_type: ElementCreateReturnType = ElementCreateReturnType.LIST,
    ):
        """
        根据xpath或cssSelector生成元素对象
        """
        browser_obj = check_element(browser_obj, None, 20)

        # 校验locate_value
        if not locate_value:
            raise BaseException(CODE_EMPTY, "定位值不能为空")

        # 发送给插件
        response = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="generateElement",
            data={"type": locate_type.value, "value": locate_value, "returnType": return_type.value},
        )

        # 判断 response 是否是列表，遍历列表，添加元素属性
        if isinstance(response, list):
            element_obj = []
            for item in response:
                element_obj.append(
                    {
                        "elementData": {
                            "app": browser_obj.browser_type.value,
                            "type": "web",
                            "picker_type": "ELEMENT",
                            "version": "1",
                            "path": item,
                        }
                    }
                )
        else:
            element_obj = {
                "elementData": {
                    "app": browser_obj.browser_type.value,
                    "type": "web",
                    "picker_type": "ELEMENT",
                    "version": "1",
                    "path": response,
                }
            }
        return element_obj

    # 根据元素对象找到关联元素
    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "relative_type",
                formType=AtomicFormTypeMeta(AtomicFormType.SELECT.value),
            ),
            atomicMg.param(
                "child_element_type",
                formType=AtomicFormTypeMeta(AtomicFormType.SELECT.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.child_element_type.show",
                        expression=f"return $this.relative_type.value == '{RelativeType.Child.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "sibling_element_type",
                formType=AtomicFormTypeMeta(AtomicFormType.SELECT.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.sibling_element_type.show",
                        expression=f"return $this.relative_type.value == '{RelativeType.Sibling.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "child_element_xpath",
                dynamics=[
                    DynamicsItem(
                        key="$this.child_element_xpath.show",
                        expression=f"return $this.child_element_type.value == '{ChildElementType.Xpath.value}' && $this.relative_type.value == '{RelativeType.Child.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "child_element_index",
                dynamics=[
                    DynamicsItem(
                        key="$this.child_element_index.show",
                        expression=f"return $this.child_element_type.value == '{ChildElementType.Index.value}' && $this.relative_type.value == '{RelativeType.Child.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "is_multiple",
                dynamics=[
                    DynamicsItem(
                        key="$this.is_multiple.show",
                        expression=f"return $this.child_element_type.value == '{ChildElementType.Xpath.value}' && $this.relative_type.value == '{RelativeType.Child.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("element_obj", types="Any")],
    )
    def get_relative_element(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        relative_type: RelativeType = RelativeType.Child,
        child_element_type: ChildElementType = ChildElementType.All,
        child_element_xpath: str = "",
        child_element_index: int = 0,
        sibling_element_type: SiblingElementType = SiblingElementType.All,
        element_timeout: int = 10,
        is_multiple: bool = False,
    ):
        """
        根据元素对象找到关联元素
        """
        browser_obj = check_element(browser_obj, element_data, element_timeout)

        element_get_type = ""
        if relative_type == RelativeType.Child:
            element_get_type = child_element_type.value
        if relative_type == RelativeType.Sibling:
            element_get_type = sibling_element_type.value

        response = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getRelativeElement",
            data={
                **element_data["elementData"]["path"],  # 解包内部字典的内容
                "relativeOptions": {
                    "relativeType": relative_type.value,
                    "index": child_element_index,
                    "xpath": child_element_xpath,
                    "elementGetType": element_get_type,
                    "multiple": is_multiple,
                },
            },
        )
        # 判断response 是否是列表
        if isinstance(response, list):
            element_obj = []
            for item in response:
                element_obj.append(
                    {
                        "elementData": {
                            "app": element_data["elementData"]["app"],
                            "version": element_data["elementData"]["version"],
                            "type": element_data["elementData"]["type"],
                            "picker_type": "ELEMENT",
                            "path": item,
                        }
                    }
                )
        else:
            element_obj = {
                "elementData": {
                    "app": element_data["elementData"]["app"],
                    "version": element_data["elementData"]["version"],
                    "type": element_data["elementData"]["type"],
                    "picker_type": "ELEMENT",
                    "path": response,
                }
            }
        return element_obj

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        outputList=[
            atomicMg.param("element_exist", types="Bool"),
        ],
    )
    def element_exist(
        browser_obj: Browser,
        element_data: WebPick,
    ) -> bool:
        """检查元素是否存在。"""
        try:
            browser_obj = check_element(browser_obj, element_data, 20)
            element_exist = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="elementIsRender",
                data=element_data["elementData"]["path"],
            )
        except Exception:
            element_exist = False
        return element_exist

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "element_data",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
            atomicMg.param(
                "check_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param("wait_time", types="Float"),
        ],
    )
    def element_visible(
        browser_obj: Browser,
        element_data: WebPick,
        check_type: ElementVisibleTypeFlag = ElementVisibleTypeFlag.VISIBLE,
        wait_time: float = 10,
    ) -> bool:
        """
        判断元素在网页中是否可见
        """
        browser_obj = check_element(browser_obj, element_data, 0)
        wait_time = max(0, float(wait_time))
        while wait_time >= 0:
            start = time.time()
            try:
                visible = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="elementIsRender",
                    data=element_data["elementData"]["path"],
                )
            except Exception:
                visible = False
            if check_type == ElementVisibleTypeFlag.VISIBLE and visible:
                return True
            if check_type == ElementVisibleTypeFlag.INVISIBLE and not visible:
                return True
            if time.time() - start >= wait_time:
                break
            time.sleep(0.3)
            wait_time = wait_time - (time.time() - start)
        return False

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "check_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
            atomicMg.param("wait_time", types="Float"),
        ],
    )
    def text_exist(
        browser_obj: Browser,
        text: str,
        check_type: WebTextExistTypeFlag = WebTextExistTypeFlag.EXIST,
        wait_time: float = 10,
    ) -> bool:
        """
        判断网页中是否包含指定文本
        """
        if not browser_obj:
            browser_obj = get_default_browser()
        js_code = "function main(){ return document.body.innerText; }" + eval_js_code(False)
        wait_time = max(0, float(wait_time))
        while wait_time >= 0:
            start = time.time()
            try:
                res = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="runJS",
                    data={"code": js_code},
                )
                page_text = str(res) if res is not None else ""
            except Exception:
                page_text = ""
            found = str(text) in page_text
            if check_type == WebTextExistTypeFlag.EXIST and found:
                return True
            if check_type == WebTextExistTypeFlag.NOT_EXIST and not found:
                return True
            if time.time() - start >= wait_time:
                break
            time.sleep(0.3)
            wait_time = wait_time - (time.time() - start)
        return False

    @staticmethod
    def _probe_element(browser_obj: Browser, element_data: WebPick) -> bool:
        """探测单个网页元素是否出现（不抛异常）"""
        if not element_data:
            return False
        try:
            return bool(
                browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="elementIsReady",
                    data=element_data["elementData"]["path"],
                )
            )
        except Exception:
            return False

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "element_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_1", types="Str", required=False),
            atomicMg.param(
                "element_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_2", types="Str", required=False),
            atomicMg.param(
                "element_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_3", types="Str", required=False),
            atomicMg.param(
                "element_4",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_4", types="Str", required=False),
            atomicMg.param(
                "element_5",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("name_5", types="Str", required=False),
            atomicMg.param("element_timeout", types="Int"),
        ],
        outputList=[
            atomicMg.param("hit_element_name", types="Str"),
            atomicMg.param("wait_result", types="Bool"),
        ],
    )
    def wait_any_element(
        browser_obj: Browser = None,
        element_1: WebPick = None,
        name_1: str = "元素1",
        element_2: WebPick = None,
        name_2: str = "元素2",
        element_3: WebPick = None,
        name_3: str = "元素3",
        element_4: WebPick = None,
        name_4: str = "元素4",
        element_5: WebPick = None,
        name_5: str = "元素5",
        element_timeout: int = 10,
    ):
        """等待任意一个元素出现（web）：轮询多个元素，任意一个出现即返回其名称"""
        candidates = [
            (element_i, name_i)
            for element_i, name_i in [
                (element_1, name_1),
                (element_2, name_2),
                (element_3, name_3),
                (element_4, name_4),
                (element_5, name_5),
            ]
            if element_i
        ]
        if not candidates:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要拾取一个元素")

        if not browser_obj:
            browser_obj = get_default_browser()

        wait_time = max(0, int(element_timeout))
        while wait_time >= 0:
            start = time.time()
            for element_i, name_i in candidates:
                if BrowserElement._probe_element(browser_obj, element_i):
                    return str(name_i), True
            if time.time() - start >= wait_time:
                break
            time.sleep(0.3)
            wait_time = wait_time - (time.time() - start)
        return "", False

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param("group_a_name", types="Str", required=False),
            atomicMg.param(
                "element_a_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_a_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_a_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("group_b_name", types="Str", required=False),
            atomicMg.param(
                "element_b_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_b_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_b_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param("element_timeout", types="Int"),
        ],
        outputList=[
            atomicMg.param("hit_group_name", types="Str"),
            atomicMg.param("wait_result", types="Bool"),
        ],
    )
    def wait_any_group(
        browser_obj: Browser = None,
        group_a_name: str = "组A",
        element_a_1: WebPick = None,
        element_a_2: WebPick = None,
        element_a_3: WebPick = None,
        group_b_name: str = "组B",
        element_b_1: WebPick = None,
        element_b_2: WebPick = None,
        element_b_3: WebPick = None,
        element_timeout: int = 10,
    ):
        """等待任意一组元素出现（web）：组内全部元素出现即该组命中，返回命中组名"""
        groups = []
        group_a = [e for e in [element_a_1, element_a_2, element_a_3] if e]
        if group_a:
            groups.append((str(group_a_name), group_a))
        group_b = [e for e in [element_b_1, element_b_2, element_b_3] if e]
        if group_b:
            groups.append((str(group_b_name), group_b))
        if not groups:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要配置一组元素")

        if not browser_obj:
            browser_obj = get_default_browser()

        wait_time = max(0, int(element_timeout))
        while wait_time >= 0:
            start = time.time()
            for group_name, group_elements in groups:
                if all(BrowserElement._probe_element(browser_obj, e) for e in group_elements):
                    return group_name, True
            if time.time() - start >= wait_time:
                break
            time.sleep(0.3)
            wait_time = wait_time - (time.time() - start)
        return "", False

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param(
                "element_1",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_2",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_3",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_4",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
            atomicMg.param(
                "element_5",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("elements", types="List"),
            atomicMg.param("element_count", types="Int"),
        ],
    )
    def combine_elements(
        element_1: WebPick = None,
        element_2: WebPick = None,
        element_3: WebPick = None,
        element_4: WebPick = None,
        element_5: WebPick = None,
    ):
        """组合多元素（web）：将拾取的多个元素合成一个元素列表"""
        elements = [e for e in [element_1, element_2, element_3, element_4, element_5] if e]
        if not elements:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "至少需要拾取一个元素")
        return elements, len(elements)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "element_data",
                formType=AtomicFormTypeMeta(type=AtomicFormType.PICK.value, params={"use": "ELEMENT"}),
            ),
        ],
        outputList=[
            atomicMg.param("lazy_elements", types="List"),
            atomicMg.param("lazy_count", types="Int"),
        ],
    )
    def get_similar_lazy(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        max_rounds: int = 20,
        stable_rounds: int = 2,
        wait_load: float = 1.0,
        max_count: int = 0,
        element_timeout: int = 10,
    ):
        """获取相似元素列表-懒加载（web）：滚动加载全部相似元素直到数量不再增长"""
        browser_obj = check_element(browser_obj, element_data, element_timeout)
        scroll_js = "function main(){ window.scrollTo(0, document.body.scrollHeight); return true; }" + eval_js_code(
            False
        )

        def query():
            data = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="elementFromSelect",
                data=element_data["elementData"]["path"],
            )
            return data or []

        elements = query()
        stable = 0
        rounds = 0
        while rounds < max(1, int(max_rounds)):
            prev = len(elements)
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="runJS",
                data={"code": scroll_js},
            )
            time.sleep(max(0.1, float(wait_load)))
            elements = query()
            if int(max_count) > 0 and len(elements) >= int(max_count):
                break
            if len(elements) == prev:
                stable += 1
                if stable >= max(1, int(stable_rounds)):
                    break
            else:
                stable = 0
            rounds += 1

        res_list = []
        for di in elements:
            res_list.append(
                {
                    "elementData": {
                        "version": element_data["elementData"]["version"],
                        "type": element_data["elementData"]["type"],
                        "app": element_data["elementData"]["app"],
                        "picker_type": "ELEMENT",
                        "path": di,
                    }
                }
            )
        return res_list, len(res_list)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("texts", types="List"),
            atomicMg.param("lazy_count", types="Int"),
        ],
    )
    def get_similar_lazy_xpath(
        browser_obj: Browser = None,
        xpath: str = "",
        max_rounds: int = 20,
        stable_rounds: int = 2,
        wait_load: float = 1.0,
        max_count: int = 0,
        element_timeout: int = 10,
    ):
        """懒加载-XPath版（web）：按XPath滚动加载全部元素并输出文本列表"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        if not browser_obj:
            browser_obj = get_default_browser()

        xpath_literal = json.dumps(str(xpath), ensure_ascii=False)
        scroll_and_count_js = (
            "function main(){ var xp="
            + xpath_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null); var n=snap.snapshotLength; window.scrollTo(0, document.body.scrollHeight); return n; }"
            + eval_js_code(False)
        )
        collect_js = (
            "function main(){ var xp="
            + xpath_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null); var out=[]; for(var i=0;i<snap.snapshotLength;i++){ var node=snap.snapshotItem(i); out.push(node.innerText||node.textContent||node.value||''); } return out; }"
            + eval_js_code(False)
        )

        def run_js(js_code):
            try:
                return browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="runJS",
                    data={"code": js_code},
                )
            except Exception:
                return None

        count = int(run_js(scroll_and_count_js) or 0)
        stable = 0
        rounds = 0
        while rounds < max(1, int(max_rounds)):
            prev = count
            time.sleep(max(0.1, float(wait_load)))
            count = int(run_js(scroll_and_count_js) or 0)
            if int(max_count) > 0 and count >= int(max_count):
                break
            if count == prev:
                stable += 1
                if stable >= max(1, int(stable_rounds)):
                    break
            else:
                stable = 0
            rounds += 1

        texts = run_js(collect_js) or []
        return texts, len(texts)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        noAdvanced=True,
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "next_xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "item_xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("page_no", types="Int"),
            atomicMg.param("page_texts", types="List"),
        ],
    )
    def paginator(
        browser_obj: Browser = None,
        next_xpath: str = "",
        item_xpath: str = "",
        max_pages: int = 0,
        wait_load: float = 1.0,
        element_timeout: int = 10,
    ):
        """翻页器-XPath（web）：循环自动翻页，每页输出页码与条目文本列表"""
        if not next_xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "下一页XPath不能为空")
        if not browser_obj:
            browser_obj = get_default_browser()

        next_literal = json.dumps(str(next_xpath), ensure_ascii=False)
        item_literal = json.dumps(str(item_xpath or ""), ensure_ascii=False)
        click_next_js = (
            "function main(){ var xp="
            + next_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null); var btn=snap.singleNodeValue; if(!btn){ return false; } btn.click(); return true; }"
            + eval_js_code(False)
        )
        collect_js = (
            "function main(){ var xp="
            + item_literal
            + "; var out=[]; if(xp){ var snap=document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null); for(var i=0;i<snap.snapshotLength;i++){ var node=snap.snapshotItem(i); out.push(node.innerText||node.textContent||node.value||''); } } return out; }"
            + eval_js_code(False)
        )

        def run_js(js_code):
            try:
                return browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="runJS",
                    data={"code": js_code},
                )
            except Exception:
                return None

        def get_iterator():
            page = 0
            while True:
                page += 1
                texts = run_js(collect_js) or []
                yield page, texts
                # 迭代恢复后再点击下一页(确保当前页处理完成)
                if int(max_pages) > 0 and page >= int(max_pages):
                    return
                if not run_js(click_next_js):
                    return
                time.sleep(max(0.1, float(wait_load)))

        return get_iterator()

    # ---------------- P3-1 Web 增强（M9） ----------------

    @staticmethod
    def _xpath_js(xpath: str, action_js: str) -> str:
        """生成 runJS 代码: 按XPath定位首个元素后执行动作JS; 元素不存在返回null"""
        xpath_literal = json.dumps(str(xpath), ensure_ascii=False)
        return (
            "function main(){ var xp="
            + xpath_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);"
            " var el=snap.singleNodeValue; if(!el){ return null; } " + action_js + " }" + eval_js_code(False)
        )

    @staticmethod
    def _run_js(browser_obj: Browser, js_code: str, time_out: float = 30):
        return browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="runJS",
            data={"code": js_code},
            timeout=float(time_out),
        )

    @staticmethod
    def _get_default_browser_or_raise(browser_obj):
        if not browser_obj:
            browser_obj = get_default_browser()
        if not browser_obj:
            raise BaseException(WEB_GET_BROWSER_ERROR, "未找到可用浏览器，请先打开或获取浏览器对象")
        return browser_obj

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("text_nodes", types="List"),
        ],
    )
    def get_text_nodes(browser_obj: Browser = None, xpath: str = ""):
        """获取文本节点内容(XPath定位元素的文本节点列表)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        xpath_literal = json.dumps(str(xpath), ensure_ascii=False)
        js_code = (
            "function main(){ var xp="
            + xpath_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);"
            " var out=[]; for(var i=0;i<snap.snapshotLength;i++){ var el=snap.snapshotItem(i);"
            " var w=document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false); var n;"
            " while((n=w.nextNode())){ var t=(n.textContent||'').trim(); if(t){ out.push(t); } } } return out; }"
            + eval_js_code(False)
        )
        data = BrowserElement._run_js(browser_obj, js_code)
        return data if isinstance(data, list) else []

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("option_text", types="Str"),
            atomicMg.param("wait_timeout", types="Int", required=False),
        ],
        outputList=[
            atomicMg.param("select_result", types="Bool"),
        ],
    )
    def universal_set_select(
        browser_obj: Browser = None,
        xpath: str = "",
        option_text: str = "",
        wait_timeout: int = 5,
    ):
        """通用设置下拉框(非select标签: 点击触发元素+按文本点击选项)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "触发元素XPath不能为空")
        if not option_text:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "选项文本不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        wait_timeout = max(1, int(wait_timeout or 5))
        xpath_literal = json.dumps(str(xpath), ensure_ascii=False)
        text_literal = json.dumps(str(option_text), ensure_ascii=False)
        js_code = (
            "async function main(){ var xp="
            + xpath_literal
            + "; var snap=document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);"
            " var el=snap.singleNodeValue; if(!el){ return false; } el.click();"
            " var txt=" + text_literal + "; var t0=Date.now();"
            " while(Date.now()-t0<__TIMEOUT_MS__){"
            ' var cands=document.querySelectorAll(\'li,[role="option"],.el-select-dropdown__item,.ant-select-item-option,.dropdown-menu li,.select-option,[class*="option"]\');'
            " var hit=null; var j;"
            " for(j=0;j<cands.length;j++){ if((cands[j].innerText||'').trim()===txt){ hit=cands[j]; break; } }"
            " if(!hit){ for(j=0;j<cands.length;j++){ if(((cands[j].innerText||'')+'').indexOf(txt)>=0){ hit=cands[j]; break; } } }"
            " if(hit){ hit.click(); return true; }"
            " await new Promise(function(r){ setTimeout(r, 300); }); } return false; }"
        ).replace("__TIMEOUT_MS__", str(wait_timeout * 1000)) + eval_js_code(True)
        return bool(BrowserElement._run_js(browser_obj, js_code, time_out=wait_timeout + 10))

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("font_color", types="Str"),
        ],
    )
    def get_font_color(browser_obj: Browser = None, xpath: str = ""):
        """获取元素字体颜色(computedStyle color)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        js_code = BrowserElement._xpath_js(xpath, "return getComputedStyle(el).color;")
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return str(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("background_color", types="Str"),
        ],
    )
    def get_background_color(browser_obj: Browser = None, xpath: str = ""):
        """获取元素背景颜色(computedStyle backgroundColor)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        js_code = BrowserElement._xpath_js(xpath, "return getComputedStyle(el).backgroundColor;")
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return str(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("background_image", types="Str"),
        ],
    )
    def get_background_image(browser_obj: Browser = None, xpath: str = ""):
        """获取元素背景图片(backgroundImage url提取, 无图返回空串)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        action_js = (
            "var bi=getComputedStyle(el).backgroundImage||''; var m=bi.match(/url\\([\"']?([^\"')]*)[\"']?\\)/);"
            " return m ? m[1] : '';"
        )
        js_code = BrowserElement._xpath_js(xpath, action_js)
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return str(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("border_width", types="Int", required=False),
            atomicMg.param("border_style", required=False),
            atomicMg.param("border_color", types="Str", required=False),
        ],
        outputList=[
            atomicMg.param("border_result", types="Bool"),
        ],
    )
    def element_add_border(
        browser_obj: Browser = None,
        xpath: str = "",
        border_width: int = 2,
        border_style: BorderStyleType = BorderStyleType.Solid,
        border_color: str = "red",
    ):
        """元素增加边框(outline实现, 不影响页面布局, 调试辅助)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        try:
            border_width = max(1, int(border_width or 2))
        except (TypeError, ValueError):
            border_width = 2
        border_literal = json.dumps("{}px {} {}".format(border_width, border_style.value, border_color))
        action_js = "el.style.outline=__BORDER__; return true;".replace("__BORDER__", border_literal)
        js_code = BrowserElement._xpath_js(xpath, action_js)
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return bool(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("show_result", types="Bool"),
        ],
    )
    def element_show(browser_obj: Browser = None, xpath: str = ""):
        """显示元素(恢复style.display)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        js_code = BrowserElement._xpath_js(xpath, "el.style.display=''; return true;")
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return bool(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("hide_result", types="Bool"),
        ],
    )
    def element_hide(browser_obj: Browser = None, xpath: str = ""):
        """隐藏元素(style.display=none)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        js_code = BrowserElement._xpath_js(xpath, "el.style.display='none'; return true;")
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return bool(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("remove_result", types="Bool"),
        ],
    )
    def element_remove(browser_obj: Browser = None, xpath: str = ""):
        """删除元素(从DOM移除, 不可恢复)"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        js_code = BrowserElement._xpath_js(xpath, "el.remove(); return true;")
        res = BrowserElement._run_js(browser_obj, js_code)
        if res is None:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        return bool(res)

    @staticmethod
    @atomicMg.atomic(
        "BrowserElement",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "image_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param("image_name", types="Str"),
        ],
        outputList=[
            atomicMg.param("long_screenshot_path", types="Str"),
        ],
    )
    def element_long_screenshot(
        browser_obj: Browser = None,
        xpath: str = "",
        image_path: str = "",
        image_name: str = "",
        scroll_step: float = 0.8,
    ):
        """元素长截图(滚动分段截取并拼接完整元素图像)"""
        import base64 as base64_module

        from PIL import Image

        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserElement._get_default_browser_or_raise(browser_obj)
        if not image_name:
            image_name = "element_long_screenshot"
        if not image_name.endswith((".png", ".jpg", ".jpeg")):
            image_name += ".png"
        dest_path = os.path.join(image_path, image_name)

        # 元素在文档中的位置与尺寸
        info_js = BrowserElement._xpath_js(
            xpath,
            "var r=el.getBoundingClientRect(); return {top:r.top+window.scrollY, left:r.left+window.scrollX,"
            " width:r.width, height:r.height, vw:window.innerWidth, vh:window.innerHeight,"
            " sy:window.scrollY};",
        )
        info = BrowserElement._run_js(browser_obj, info_js)
        if not isinstance(info, dict):
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素未找到")
        elem_top = float(info.get("top", 0))
        elem_left = float(info.get("left", 0))
        elem_w = float(info.get("width", 0))
        elem_h = float(info.get("height", 0))
        vh = max(100.0, float(info.get("vh", 800)))
        if elem_h <= 0 or elem_w <= 0:
            raise BaseException(WEB_GET_ELE_ERROR.format(xpath), "元素尺寸无效")

        step = max(100.0, vh * max(0.2, min(1.0, float(scroll_step or 0.8))))
        origin_y = float(info.get("sy", 0))
        pieces = []
        y = elem_top
        try:
            while y < elem_top + elem_h:
                scroll_js = "function main(){ window.scrollTo(0, __Y__); return true; }".replace(
                    "__Y__", str(int(y))
                ) + eval_js_code(False)
                BrowserElement._run_js(browser_obj, scroll_js)
                time.sleep(0.25)
                data = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value,
                    key="captureScreen",
                    data={"": ""},
                )
                if not data:
                    raise BaseException(BROWSER_EXTENSION_ERROR_FORMAT.format("截图返回数据为空"), "元素长截图失败")
                data = str(data).replace("data:image/jpeg;base64,", "").replace("data:image/png;base64,", "")
                img = Image.open(__import__("io").BytesIO(base64_module.b64decode(data)))
                # 本段负责的元素区间: [y, y+min(step, 剩余高度)], 截图顶部=当前视口顶
                scroll_y = y
                seg_bottom = min(float(img.height), elem_top + elem_h - scroll_y, step)
                if seg_bottom < 1:
                    y += step
                    continue
                crop_box = (
                    int(max(0, elem_left)),
                    0,
                    int(min(float(img.width), elem_left + elem_w)),
                    int(seg_bottom),
                )
                pieces.append(img.crop(crop_box))
                y += step
            if not pieces:
                raise BaseException(BROWSER_EXTENSION_ERROR_FORMAT.format("未截取到元素内容"), "元素长截图失败")
            total_h = sum(p.height for p in pieces)
            merged = Image.new("RGB", (int(elem_w), total_h))
            offset = 0
            for p in pieces:
                merged.paste(p, (0, offset))
                offset += p.height
            merged.save(dest_path)
        finally:
            # 回滚原始滚动位置
            restore_js = "function main(){ window.scrollTo(0, __Y__); return true; }".replace(
                "__Y__", str(int(origin_y))
            ) + eval_js_code(False)
            try:
                BrowserElement._run_js(browser_obj, restore_js)
            except Exception:
                pass
        return dest_path
