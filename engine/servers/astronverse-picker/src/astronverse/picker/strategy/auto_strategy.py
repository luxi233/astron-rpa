import traceback
from _ctypes import COMError
from typing import TYPE_CHECKING, Optional

from astronverse.picker import APP, IElement
from astronverse.picker.engines.uia_picker import UIAOperate
from astronverse.picker.logger import logger

if TYPE_CHECKING:
    from astronverse.picker.strategy.types import Strategy, StrategySvc
    from astronverse.picker.svc import ServiceContext


def auto_default_strategy(
    service: "ServiceContext", strategy: "Strategy", strategy_svc: "StrategySvc"
) -> Optional[IElement]:
    """自动选择策略"""

    # 延迟导入策略函数避免循环依赖
    from astronverse.picker.strategy.msaa_strategy import msaa_default_strategy
    from astronverse.picker.strategy.uia_strategy import uia_default_strategy
    from astronverse.picker.strategy.web_strategy import web_default_strategy

    # 注意: JAB(Java)/SAP/IE 拾取策略模块当前未实现(历史代码曾引用 jab_strategy/
    # sap_default_strategy/web_ie_strategy, 均不存在于仓库)。相关场景显式告警后
    # 降级 UIA, 不再静默吞 NameError

    # 2. 浏览器优先走 DOM 拾取
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
                    # IE 拾取策略未实现, 不再静默返回 None; 明确告警后降级 UIA
                    logger.warning(
                        "IE 内核页面暂不支持元素级拾取(拾取策略未实现), 已降级为 UIA 拾取; 如需精确定位请使用 CV 图像拾取"
                    )
                    return None
                else:
                    web_cache = (is_document, menu_top, menu_left, hwnd)
                    # web元素直接返回，不做兜底
                    return web_default_strategy(service, strategy_svc, web_cache)
        except COMError as e:
            # 忽略所有 COM 调用错误
            logger.warning(f"忽略 COMError: {e}")
            logger.debug("COMError 堆栈信息:\n{}".format(traceback.format_exc()))
            return None
        except Exception as e:
            logger.error("堆栈信息:\n%s", traceback.format_exc())
            logger.error(f"auto_default_strategy web error: {e} {traceback.extract_stack()}")
            raise e
    elif strategy_svc.app == APP.SAP:
        # 2. 判断是否是sap: SAP 拾取策略未实现, 显式告警后降级 UIA
        logger.warning("SAP GUI 拾取策略未实现, 已降级为 UIA 拾取; 若控件无法捕获请使用 UIA 深度拾取或 CV 图像拾取")

    # 3. 桌面标准模式: UIA + MSAA 并行试探(原 MSAA 白名单已移除,
    # 将 Thunder 类应用的"双域试探择优"泛化到所有桌面应用;
    # 老旧软件(MFC/VB/Delphi等)UIA 往往失败, MSAA 是重要捕获通道)
    msaa_element = None
    try:
        msaa_element = msaa_default_strategy(strategy_svc)
    except Exception as e:
        logger.warning(f"标准模式 MSAA 试探异常, 忽略并继续 UIA: {e}")

    uia_element = None
    try:
        uia_element = uia_default_strategy(strategy_svc)
    except Exception as e:
        logger.error("堆栈信息:\n%s", traceback.format_exc())
        logger.error(f"auto_default_strategy uia_picker error: {e} {traceback.extract_stack()}")

    # 4. 结果择优: 双成功取面积小者(更贴近真实控件), 单成功直接返回
    if uia_element is None:
        return msaa_element
    if msaa_element is None:
        return uia_element
    logger.info(
        "pk: uia %s msaa %s",
        uia_element.rect().area(),
        msaa_element.rect().area(),
    )
    if msaa_element.rect().area() <= uia_element.rect().area():
        return msaa_element
    return uia_element
