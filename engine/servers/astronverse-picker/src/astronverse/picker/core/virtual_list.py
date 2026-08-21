"""虚拟列表批量采集模块(E4)。

虚拟列表(懒加载/虚拟化)同一时刻仅渲染可视区内的条目, 一次性采集不全。
本模块对容器执行"采集→滚动→再采集"循环, 按结构指纹去重, 直至滚动到底或无新增条目。
"""

from typing import Callable, Optional

from astronverse.picker.logger import logger

# 默认最大滚动次数(不含首屏)
DEFAULT_MAX_SCROLLS = 5
# 滚轮兜底单次滚动量(负值向下/向右)
WHEEL_SCROLL_AMOUNT = -3


def _safe(control, attr: str):
    try:
        value = getattr(control, attr)
        return str(value) if value else None
    except Exception:
        return None


def item_fingerprint(control) -> tuple:
    """条目结构指纹: 用于跨屏去重。

    优先 (tag, cls, name, automation_id); 均无区分属性时退化为 rect,
    避免所有空属性条目被误判为同一条目。
    """
    tag = _safe(control, "ControlTypeName")
    cls = _safe(control, "ClassName")
    name = _safe(control, "Name")
    auto_id = _safe(control, "AutomationId")
    if name or auto_id:
        return (tag, cls, name, auto_id)
    try:
        rect = control.BoundingRectangle
        return (tag, cls, "rect", rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return (tag, cls, None, None)


def _first_child_fingerprint(container):
    """首个可见子控件指纹: 无 ScrollPattern 时用于判断滚轮是否生效"""
    try:
        children = container.GetChildren()
        if children:
            return item_fingerprint(children[0])
    except Exception:
        pass
    return None


def _wheel_scroll(container, horizontal: bool) -> bool:
    """滚轮兜底滚动: 容器不支持 ScrollPattern 时, 用 pyautogui 在容器中心发滚轮事件。

    Returns:
        True 滚动生效(首屏条目变化); False 依赖缺失或滚动未生效
    """
    try:
        import pyautogui
    except ImportError as e:
        logger.warning(f"滚轮兜底滚动不可用(pyautogui 缺失): {e}")
        return False
    try:
        rect = container.BoundingRectangle
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
    except Exception as e:
        logger.warning(f"滚轮兜底滚动失败: 无法读取容器区域: {e}")
        return False
    before = _first_child_fingerprint(container)
    try:
        pyautogui.moveTo(cx, cy)
        if horizontal:
            # pyautogui 无原生横向滚轮, 用 shift+滚轮模拟(多数 Windows 控件支持)
            pyautogui.hotkey("shift", "scroll", clicks=WHEEL_SCROLL_AMOUNT)
        else:
            pyautogui.scroll(WHEEL_SCROLL_AMOUNT)
    except Exception as e:
        logger.warning(f"滚轮兜底滚动异常: {e}")
        return False
    after = _first_child_fingerprint(container)
    if after is not None and after == before:
        logger.info("滚轮滚动后首条目未变化, 判定已到底或滚动未生效")
        return False
    return True


def default_scroll(container, horizontal: bool = False) -> bool:
    """默认滚动实现: 优先 UIA ScrollPattern 翻页, 不支持时滚轮兜底。

    Args:
        container: 列表容器控件
        horizontal: True 横向滚动(右), False 纵向滚动(下)

    Returns:
        True 滚动生效(位置前进); False 滚动不支持或已到底
    """
    try:
        import uiautomation as auto

        pattern = container.GetScrollPattern()
        if pattern is not None:
            if horizontal:
                if not getattr(pattern, "CurrentHorizontallyScrollable", False):
                    logger.info("容器不支持横向 ScrollPattern, 尝试滚轮兜底")
                    return _wheel_scroll(container, horizontal=True)
                before = pattern.CurrentHorizontalScrollPercent
                pattern.Scroll(auto.ScrollAmount.LargeIncrement, auto.ScrollAmount.NoAmount)
                after = pattern.CurrentHorizontalScrollPercent
            else:
                before = pattern.CurrentVerticalScrollPercent
                pattern.Scroll(auto.ScrollAmount.NoAmount, auto.ScrollAmount.LargeIncrement)
                after = pattern.CurrentVerticalScrollPercent
            if after <= before + 1e-6:
                logger.info("滚动后位置未变化, 判定已到达列表底部")
                return False
            return True
        logger.info("容器不支持 ScrollPattern, 尝试滚轮兜底滚动")
        return _wheel_scroll(container, horizontal=horizontal)
    except Exception as e:
        logger.warning(f"虚拟列表滚动异常, 停止滚动采集: {e}")
        return False


def collect_virtual_list(
    container,
    is_item: Optional[Callable] = None,
    scroll_fn: Optional[Callable] = None,
    max_scrolls: int = DEFAULT_MAX_SCROLLS,
    horizontal: bool = False,
) -> list:
    """滚动容器分批续采相似条目。

    Args:
        container: 列表容器控件
        is_item: 条目判定函数, 缺省视为所有直接子控件
        scroll_fn: 滚动函数(container) -> bool(是否生效), 缺省走 ScrollPattern(不支持时滚轮兜底)
        max_scrolls: 最大滚动次数(首屏不计)
        horizontal: True 横向滚动采集(默认滚动实现时生效)

    Returns:
        去重后的条目控件列表(按首次出现顺序)
    """
    if container is None:
        raise Exception("虚拟列表采集失败: 未获取到容器控件")
    if is_item is None:
        is_item = lambda child: True  # noqa: E731

    def scroll(container):
        # 调用时解析模块属性, 保持 monkeypatch default_scroll 可测试性;
        # horizontal 仅默认实现支持, 外部自定义 scroll_fn 保持单参签名
        if scroll_fn is not None:
            return scroll_fn(container)
        return globals()["default_scroll"](container, horizontal=horizontal)

    seen = set()
    items = []
    scrolls = max(0, int(max_scrolls))
    step = 0
    while True:
        new_count = 0
        try:
            children = container.GetChildren()
        except Exception:
            children = []
        for child in children:
            try:
                if not is_item(child):
                    continue
                fp = item_fingerprint(child)
                if fp in seen:
                    continue
                seen.add(fp)
                items.append(child)
                new_count += 1
            except Exception as e:
                logger.warning(f"虚拟列表条目采集异常, 已跳过: {e}")

        if step >= scrolls:
            break
        if not scroll(container):
            break
        if new_count == 0:
            logger.info("滚动后无新增条目, 判定采集完成")
            break
        step += 1

    logger.info(f"虚拟列表采集完成: 共 {len(items)} 条, 采集 {step + 1} 屏")
    return items
