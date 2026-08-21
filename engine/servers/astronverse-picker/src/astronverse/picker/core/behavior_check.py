"""E5 行为校验: 非破坏性操作能力检查。

原行为校验(click/input/hover)需要真实执行合成事件, 因事件失真与副作用被注释下线。
本模块改为"能力校验": 不执行任何事件, 仅依据 UIA 控件属性判断元素是否
可点击/可输入/可悬停, 无副作用且不受合成事件失真影响。
"""

from typing import Tuple

from astronverse.picker.logger import logger

# 校验模式(与前端 VALID_OPTIONS 取值一致)
VALID_POSITION = "check_position"
VALID_CLICK = "check_click"
VALID_INPUT = "check_input"
VALID_HOVER = "check_hover"


def _bool_prop(control, prop: str) -> bool:
    """读取 UIA 布尔属性(兼容 property/method 两种形态), 无法判定时按 True 放行"""
    try:
        value = getattr(control, prop)
        return bool(value() if callable(value) else value)
    except Exception:
        return True


def _rect_ok(control) -> Tuple[bool, str]:
    try:
        rect = control.BoundingRectangle
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return False, f"元素区域无效({width}x{height}), 可能被折叠或隐藏"
        return True, ""
    except Exception as e:
        return False, f"无法读取元素区域: {e}"


def check_clickable(control) -> Tuple[bool, str]:
    """可点击: 区域有效 + 未禁用 + 不在屏幕外"""
    ok, reason = _rect_ok(control)
    if not ok:
        return False, reason
    if not _bool_prop(control, "IsEnabled"):
        return False, "元素处于禁用状态(IsEnabled=False), 无法点击"
    if _bool_prop(control, "IsOffscreen"):
        return False, "元素位于屏幕外(IsOffscreen=True), 需先滚动到可视区域"
    return True, "元素可点击"


def check_inputable(control) -> Tuple[bool, str]:
    """可输入: 区域有效 + 未禁用 + 支持 ValuePattern 或 TextPattern"""
    ok, reason = _rect_ok(control)
    if not ok:
        return False, reason
    if not _bool_prop(control, "IsEnabled"):
        return False, "元素处于禁用状态(IsEnabled=False), 无法输入"
    for pattern_getter in ("GetValuePattern", "GetTextPattern"):
        try:
            pattern = getattr(control, pattern_getter)()
            if pattern is not None:
                return True, "元素可输入"
        except Exception:
            continue
    return False, "元素不支持输入(无 Value/Text Pattern), 请确认拾取的是输入框本身"


def check_hoverable(control) -> Tuple[bool, str]:
    """可悬停: 区域有效 + 不在屏幕外(悬停不要求 enabled)"""
    ok, reason = _rect_ok(control)
    if not ok:
        return False, reason
    if _bool_prop(control, "IsOffscreen"):
        return False, "元素位于屏幕外(IsOffscreen=True), 需先滚动到可视区域"
    return True, "元素可悬停"


CHECKERS = {
    VALID_CLICK: check_clickable,
    VALID_INPUT: check_inputable,
    VALID_HOVER: check_hoverable,
}


def run_behavior_check(control, mode: str) -> Tuple[bool, str]:
    """执行行为校验, 未知模式按位置校验放行。

    Returns:
        (通过与否, 结论说明)
    """
    checker = CHECKERS.get(mode)
    if checker is None:
        return True, "位置校验"
    try:
        ok, reason = checker(control)
        logger.info(f"行为校验[{mode}]: {'通过' if ok else '未通过'} - {reason}")
        return ok, reason
    except Exception as e:
        logger.warning(f"行为校验[{mode}]执行异常: {e}")
        return False, f"行为校验执行异常: {e}"
