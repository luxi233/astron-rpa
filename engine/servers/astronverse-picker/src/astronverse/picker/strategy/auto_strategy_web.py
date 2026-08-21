import traceback
from _ctypes import COMError
from typing import TYPE_CHECKING, Optional

from astronverse.picker import APP, IElement
from astronverse.picker.engines.uia_picker import UIAOperate
from astronverse.picker.logger import logger

if TYPE_CHECKING:
    from astronverse.picker.strategy.types import Strategy, StrategySvc
    from astronverse.picker.svc import ServiceContext


def auto_default_strategy_web(
    service: "ServiceContext", strategy: "Strategy", strategy_svc: "StrategySvc"
) -> Optional[IElement]:
    """自动选择策略"""

    # 延迟导入策略函数避免循环依赖
    from astronverse.picker.strategy.web_strategy import web_default_strategy

    # 注意: web_ie_strategy 模块当前未实现(历史代码曾引用但仓库中不存在),
    # IE 场景显式告警后返回 None, 不再静默吞 NameError

    # 2. 获取可能的元素
    preliminary_element = None
    chrome_like_apps = [
        APP.Chrome,
        APP.Firefox,
        APP.Chrome360X,
        APP.Chrome360se,
        APP.Chrome360,
        APP.Edge,
        APP.IE,
        APP.Chromium,
    ]
    if strategy_svc.app in chrome_like_apps:
        # 1. 如果是浏览器优先使用浏览器获取
        try:
            try:
                web_control_result = UIAOperate().get_web_control(
                    strategy_svc.start_control,
                    strategy_svc.app,
                    strategy_svc.last_point,
                )
                is_document, menu_top, menu_left, hwnd = web_control_result
            except Exception as e:
                logger.error("堆栈信息:\n{}".format(traceback.format_exc()))
                return None

            if is_document:
                if strategy_svc.app == APP.IE:
                    # IE 拾取策略未实现, 明确告警而非静默返回 None
                    logger.warning("IE 内核页面暂不支持元素级拾取(拾取策略未实现); 如需精确定位请使用 CV 图像拾取")
                    return None
                else:
                    web_cache = (is_document, menu_top, menu_left, hwnd)
                    preliminary_element = web_default_strategy(service, strategy_svc, web_cache)
                # web元素直接返回，不做兜底
                return preliminary_element
        except COMError as e:
            # 忽略所有 COM 调用错误
            logger.warning(f"忽略 COMError: {e}")
            logger.debug("COMError 堆栈信息:\n{}".format(traceback.format_exc()))
            return None
        except Exception as e:
            logger.error("堆栈信息:\n%s", traceback.format_exc())
            logger.error(f"auto_default_strategy web error: {e} {traceback.extract_stack()}")
            raise e
    return None
