"""浏览器元素断言: 等待元素出现，超时未出现时抛出异常中断流程"""

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import WebPick
from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.browser import WaitElementForStatusFlag
from astronverse.browser.browser import Browser
from astronverse.browser.browser_element import BrowserElement

__all__ = ["Assert"]


class Assert:
    @staticmethod
    @atomicMg.atomic(
        "Assert",
        inputList=[
            atomicMg.param("browser_obj", types="Str"),
            atomicMg.param("element_data", types="Str"),
            atomicMg.param(
                "wait_time",
                types="Int",
                required=False,
            ),
            atomicMg.param(
                "error_message",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
        ],
    )
    def assert_element(
        browser_obj: Browser = None,
        element_data: WebPick = None,
        wait_time: int = 10,
        error_message: str = "",
    ) -> None:
        """
        元素断言(等待网页元素出现，超时未出现时抛出异常并中断流程)
        :param browser_obj: 浏览器对象(不选则使用已打开的浏览器)
        :param element_data: 网页元素
        :param wait_time: 等待时间(秒)
        :param error_message: 断言失败时的自定义错误信息(不填使用默认信息)
        """
        if wait_time < 0:
            wait_time = 10
        if not browser_obj:
            from astronverse.browser.browser_element import get_default_browser

            browser_obj = get_default_browser()
        appeared = BrowserElement.wait_element(
            browser_obj=browser_obj,
            element_data=element_data,
            ele_status=WaitElementForStatusFlag.ElementExists,
            element_timeout=wait_time,
        )
        if not appeared:
            if error_message:
                raise BaseException(
                    ErrorCode(BizCode.LocalErr, error_message), "元素断言失败: 等待{}秒后元素仍未出现".format(wait_time)
                )
            raise BaseException(
                ErrorCode(BizCode.LocalErr, "元素断言失败，流程已中断"),
                "等待{}秒后元素仍未出现".format(wait_time),
            )
