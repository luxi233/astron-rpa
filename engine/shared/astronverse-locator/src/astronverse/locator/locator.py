"""
定位器管理模块

提供统一的元素定位管理功能，支持多种定位器类型。
"""

import json
import re
import time
import traceback
from typing import Union

from astronverse.baseline.logger.logger import logger
from astronverse.locator import ILocator, PickerDomain, PickerType
from astronverse.locator.core import heal_store


def uia_factory_callback():
    """获取UIA定位器工厂的回调函数"""
    from astronverse.locator.core.uia_locator import (
        uia_factory,
    )

    return uia_factory.find


def web_factory_callback():
    """获取Web定位器工厂的回调函数"""
    from astronverse.locator.core.web_locator import (
        web_factory,
    )

    return web_factory.find


def msaa_factory_callback():
    """获取MSAA定位器工厂的回调函数"""
    from astronverse.locator.core.msaa_locator import (
        msaa_factory,
    )

    return msaa_factory.find


def web_ie_factory_callback():
    """IE 内核页面元素定位回调。

    web_ie_locator 专用定位器未实现(仓库中不存在该模块);
    IE 页面元素拾取时 type 统一为 web, 此处直接委托 web 定位器兼容处理。
    """
    logger.warning("IE 专用定位器未实现, 已委托 Web 定位器兼容处理; 如定位失败请改用 CV 图像定位")
    from astronverse.locator.core.web_locator import (
        web_factory,
    )

    return web_factory.find


def jab_factory_callback():
    """JAB(Java Accessibility) 元素定位回调。

    jab_locator 专用定位器未实现(仓库中不存在该模块), 显式告警后委托 UIA 定位器,
    不再通过 try/except 静默吞导入异常。
    """
    logger.warning("JAB 定位器未实现, 已使用 UIA 定位器兼容处理; 若 Java 控件无法捕获请尝试 UIA 深度拾取或 CV 图像拾取")
    from astronverse.locator.core.uia_locator import (
        uia_factory,
    )

    return uia_factory.find


def sap_factory_callback():
    """SAP GUI 元素定位回调。

    sap_locator 专用定位器未实现(仓库中不存在该模块), 显式告警后委托 UIA 定位器,
    不再通过 try/except 静默吞导入异常。
    """
    logger.warning("SAP 定位器未实现, 已使用 UIA 定位器兼容处理; 若 SAP 控件无法捕获请尝试 UIA 深度拾取或 CV 图像拾取")
    from astronverse.locator.core.uia_locator import (
        uia_factory,
    )

    return uia_factory.find


class LocatorManager:
    """管理器"""

    def __init__(self):
        self.locator_handler = {
            PickerDomain.UIA.value: [uia_factory_callback],
            PickerDomain.WEB.value: [web_factory_callback],
            # 存量 web_ie 类型元素委托 web 定位器, 保留入口避免 KeyError
            PickerDomain.WEB_IE.value: [web_ie_factory_callback],
            PickerDomain.MSAA.value: [msaa_factory_callback],
            PickerDomain.JAB.value: [jab_factory_callback],
            PickerDomain.SAP.value: [sap_factory_callback],
        }

    @staticmethod
    def parse_element_json(element_string):
        """
        使用正则匹配出里面的img图片过滤掉

        Args:
            element_string: 元素字符串

        Returns:
            解析后的元素字典
        """
        try:
            img_match = re.search(r'(,"img".*})}$', element_string)
            if img_match:
                dictionary_string = element_string[0 : img_match.regs[1][0]] + "}"
                image_dictionary_string = img_match.group(1)[7:]
                dictionary_json = json.loads(dictionary_string)
                image_dictionary = json.loads(image_dictionary_string)
                dictionary_json["img"] = image_dictionary
                return dictionary_json
        except Exception:
            pass
        return json.loads(element_string)

    def locator(self, element: Union[str, dict], **kwargs) -> Union[list[ILocator], ILocator, None]:
        """
        定位元素

        Args:
            element: 元素信息，可以是字符串或字典
            **kwargs: 额外参数, 另支持:
                report(dict): 传入时回写自愈/CV 降级信息供上层展示
                self_heal/cv_fallback: 缺省开启的降级开关

        Returns:
            定位器对象或定位器列表
        """
        start_ts = time.perf_counter()
        heal_store.record_metric("locate_total")

        # 读取element
        if isinstance(element, str):
            element = self.parse_element_json(element)

        # 元素公共配置
        locator_type = element.get("type", PickerDomain.UIA.value)
        picker_type = element.get("picker_type", "")
        report = kwargs.get("report")
        heal_eligible = kwargs.get("self_heal", True) and locator_type == PickerDomain.UIA.value and not picker_type
        # report 仅供上层回写, 不透传给定位器回调
        handler_kwargs = {k: v for k, v in kwargs.items() if k != "report"}

        try:
            # 自愈缓存快路径: 上次自愈成功的修复版路径直接复用, 免重复探索
            if heal_eligible:
                healed_path = heal_store.heal_cache_get(element)
                if healed_path is not None:
                    cached_element = dict(element)
                    cached_element["path"] = healed_path
                    try:
                        cached_result = self._run_handlers(cached_element, picker_type, handler_kwargs)
                    except Exception as e:
                        logger.warning(f"自愈缓存定位异常, 移除该缓存: {e}")
                        cached_result = None
                    if cached_result is not None:
                        heal_store.record_metric("heal_cache_hit")
                        if isinstance(report, dict):
                            report["heal_cache"] = True
                        return cached_result
                    heal_store.heal_cache_drop(element)
                    heal_store.record_metric("heal_cache_invalidated")

            result = self._run_handlers(element, picker_type, handler_kwargs, collect_error=True)
            if not isinstance(result, tuple):
                return result
            last_error = result[0]

            # E2 selector 自愈: 定位失败后渐进放宽匹配条件重试(仅 UIA 常规定位, SIMILAR 自带降级链)
            if heal_eligible:
                from astronverse.locator.core.uia_locator import UIAFactory

                heal_store.record_metric("heal_attempt")
                heal_kwargs = {k: v for k, v in handler_kwargs.items() if k != "self_heal"}
                heal_result = UIAFactory.heal(element, picker_type=picker_type, **heal_kwargs)
                if heal_result["healed"]:
                    # 持久化修复结果: 下次定位走缓存快路径, 不再重复自愈探索
                    heal_store.heal_cache_put(element, heal_result["element"]["path"], heal_result["relaxations"])
                    heal_store.record_metric("heal_success")
                    if isinstance(report, dict):
                        report["healed"] = True
                        report["relaxations"] = heal_result["relaxations"]
                        report["repair_hint"] = heal_result["repair_hint"]
                    return heal_result["locator"]
                if heal_result["relaxations"]:
                    logger.warning(
                        f"selector 自愈失败(已尝试 {len(heal_result['relaxations'])} 级放宽): 建议重新拾取该元素或改用 CV 图像定位"
                    )

            # E3 元素+图像融合降级: 自愈仍未命中且元素携带拾取截图时, 切 CV 模板匹配
            if kwargs.get("cv_fallback", True) and locator_type == PickerDomain.UIA.value and not picker_type:
                from astronverse.locator.core.cv_fallback import cv_fallback as _cv_fallback

                heal_store.record_metric("cv_fallback_attempt")
                # report 传入以回写歧义候选数等降级状态(歧义时仍返回 None 走常规报错链)
                fallback = _cv_fallback(element, report=report)
                if fallback is not None:
                    heal_store.record_metric("cv_fallback_success")
                    if isinstance(report, dict):
                        report["cv_fallback"] = True
                    return fallback

            if last_error:
                raise last_error
            return None
        finally:
            heal_store.record_timing((time.perf_counter() - start_ts) * 1000)

    def _run_handlers(self, element: dict, picker_type: str, kwargs: dict, collect_error: bool = False):
        """依次执行定位器回调。命中返回结果; 未命中时 collect_error=True 返回 (last_error,) 元组, 否则 None"""
        locator_type = element.get("type", PickerDomain.UIA.value)
        last_error = None
        for callback in self.locator_handler[locator_type]:
            try:
                callback_func = callback()
                if callback_func is None:
                    continue
                result = callback_func(ele=element, picker_type=picker_type, **kwargs)
                if result is not None:
                    heal_store.record_metric("locate_success")
                    return result
            except Exception as exception:
                last_error = exception
                logger.error(f"Strategy run error: {exception} {traceback.format_exc()}")
        heal_store.record_metric("locate_fail")
        if collect_error:
            return (last_error,)
        return None


locator = LocatorManager()
