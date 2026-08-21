import traceback
from typing import TYPE_CHECKING, Optional

from astronverse.picker import APP, IElement
from astronverse.picker.logger import logger

if TYPE_CHECKING:
    from astronverse.picker.strategy.types import Strategy, StrategySvc
    from astronverse.picker.svc import ServiceContext


def auto_default_strategy_desk(
    service: "ServiceContext", strategy: "Strategy", strategy_svc: "StrategySvc"
) -> Optional[IElement]:
    """自动选择策略"""

    # 延迟导入策略函数避免循环依赖
    from astronverse.picker.strategy.msaa_strategy import msaa_default_strategy
    from astronverse.picker.strategy.uia_strategy import uia_default_strategy

    # 注意: JAB(Java)/SAP 拾取策略模块当前未实现(历史代码曾引用 jab_strategy/
    # sap_default_strategy, 均不存在于仓库)。相关场景显式告警后降级 UIA,
    # 不再静默吞 NameError

    # 桌面标准模式: UIA + MSAA 并行试探(与 AUTO 策略对齐; 原 MSAA 白名单已移除,
    # 老旧软件(MFC/VB/Delphi等非标准控件)UIA 往往失败, MSAA 是重要捕获通道)
    if strategy_svc.app == APP.SAP:
        # 判断是否是sap: SAP 拾取策略未实现, 显式告警后降级 UIA
        logger.warning("SAP GUI 拾取策略未实现, 已降级为 UIA 拾取; 若控件无法捕获请使用 UIA 深度拾取或 CV 图像拾取")

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

    # 结果择优: 双成功取面积小者(更贴近真实控件), 单成功直接返回
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
