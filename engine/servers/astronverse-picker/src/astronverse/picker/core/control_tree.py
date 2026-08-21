"""控件树导出模块(E1 控件树浏览器后端能力)。

将 UIA 控件树序列化为 JSON 结构, 供前端树形浏览器渲染与点选拾取。
导出带深度上限与节点总数上限, 防止深树/大树雪崩。
"""

from typing import Optional

from astronverse.picker.logger import logger

# 默认导出深度上限
DEFAULT_MAX_DEPTH = 6
# 单次导出节点总数上限
MAX_NODE_COUNT = 2000


def _safe_attr(control, attr: str) -> Optional[str]:
    try:
        value = getattr(control, attr)
        return str(value) if value else None
    except Exception:
        return None


def _safe_rect(control) -> Optional[dict]:
    try:
        rect = control.BoundingRectangle
        return {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
    except Exception:
        return None


def _dump_node(control, max_depth: int, depth: int, counter: list) -> Optional[dict]:
    if counter[0] >= MAX_NODE_COUNT:
        return None
    counter[0] += 1

    node = {
        "tag_name": _safe_attr(control, "ControlTypeName"),
        "cls": _safe_attr(control, "ClassName"),
        "name": _safe_attr(control, "Name"),
        "automation_id": _safe_attr(control, "AutomationId"),
        "rect": _safe_rect(control),
        "children": [],
    }

    if depth < max_depth:
        try:
            children = control.GetChildren()
        except Exception:
            children = []
        for child in children:
            if counter[0] >= MAX_NODE_COUNT:
                logger.warning(f"控件树导出达到节点上限 {MAX_NODE_COUNT}, 已截断")
                break
            child_node = _dump_node(child, max_depth, depth + 1, counter)
            if child_node is not None:
                node["children"].append(child_node)
    return node


def dump_control_tree(control, max_depth: int = DEFAULT_MAX_DEPTH) -> dict:
    """导出以 control 为根的控件树。

    Args:
        control: UIA 控件对象
        max_depth: 最大导出深度(根节点为第1层)

    Returns:
        树形 dict, 每个节点含 tag_name/cls/name/automation_id/rect/children
    """
    if control is None:
        raise Exception("控件树导出失败: 未获取到根控件")
    if max_depth < 1:
        max_depth = 1
    counter = [0]
    tree = _dump_node(control, max_depth, 1, counter)
    logger.info(f"控件树导出完成: 深度上限 {max_depth}, 共 {counter[0]} 个节点")
    return tree
