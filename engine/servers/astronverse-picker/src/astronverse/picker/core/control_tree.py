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

# 实时树(深度捕获侧边面板)参数: 聚焦链每层兄弟窗口半径/聚焦点子树深度/节点总数上限
LIVE_SIBLING_SPAN = 3
LIVE_CHILD_DEPTH = 2
LIVE_MAX_NODE_COUNT = 300


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


# ============================================================================
# 实时局部树(深度捕获侧边面板, 随鼠标移动增量推送)
# ============================================================================


def _safe_runtime_id(control) -> str:
    try:
        return "-".join(str(x) for x in control.GetRuntimeId())
    except Exception:
        return ""


def _live_node(control, focused: bool = False) -> dict:
    """构造实时树节点, 字段与 ControlTreeNode 对齐, 另加 id/focused"""
    return {
        "id": _safe_runtime_id(control),
        "tag_name": _safe_attr(control, "ControlTypeName"),
        "cls": _safe_attr(control, "ClassName"),
        "name": _safe_attr(control, "Name"),
        "automation_id": _safe_attr(control, "AutomationId"),
        "rect": _safe_rect(control),
        "focused": focused,
        "children": [],
    }


def _safe_children(control) -> list:
    try:
        return list(control.GetChildren())
    except Exception:
        return []


def _build_focus_children(control, remaining_depth: int, sibling_span: int, counter: list) -> list:
    """聚焦节点的浅层子树(children 全量 + 递归深度受限)"""
    if remaining_depth <= 0 or counter[0] >= LIVE_MAX_NODE_COUNT:
        return []
    nodes = []
    for child in _safe_children(control):
        if counter[0] >= LIVE_MAX_NODE_COUNT:
            logger.warning(f"实时树导出达到节点上限 {LIVE_MAX_NODE_COUNT}, 已截断")
            break
        counter[0] += 1
        node = _live_node(child)
        node["children"] = _build_focus_children(child, remaining_depth - 1, sibling_span, counter)
        nodes.append(node)
    return nodes


def _build_ancestor_level(ancestor, chain: list, idx: int, sibling_span: int, counter: list):
    """沿祖先链向下构造: 每层 = 聚焦链上的子节点 + 其前后各 sibling_span 个兄弟节点

    返回当前层节点, 节点总数超限时返回 None(调用方标记 truncated)。
    """
    node = _live_node(ancestor, focused=idx == len(chain) - 1)
    children_src = _safe_children(ancestor)

    if idx == len(chain) - 1:
        # 聚焦节点: 展开浅层子树
        node["children"] = _build_focus_children(ancestor, LIVE_CHILD_DEPTH, sibling_span, counter)
        return node

    focus_child = chain[idx + 1]
    try:
        focus_idx = children_src.index(focus_child)
    except ValueError:
        # 句柄/代理对象不相等时退回 RuntimeId 匹配
        focus_id = _safe_runtime_id(focus_child)
        focus_idx = next((i for i, c in enumerate(children_src) if _safe_runtime_id(c) == focus_id), -1)

    # 兄弟窗口裁剪: 聚焦子节点前后各保留 sibling_span 个
    if focus_idx >= 0:
        lo = max(0, focus_idx - sibling_span)
        hi = min(len(children_src), focus_idx + sibling_span + 1)
        windowed = children_src[lo:hi]
    else:
        windowed = children_src[: sibling_span + 1]

    for child in windowed:
        if counter[0] >= LIVE_MAX_NODE_COUNT:
            logger.warning(f"实时树导出达到节点上限 {LIVE_MAX_NODE_COUNT}, 已截断")
            break
        counter[0] += 1
        if child is focus_child or (focus_idx < 0 and _safe_runtime_id(child) == _safe_runtime_id(focus_child)):
            child_node = _build_ancestor_level(focus_child, chain, idx + 1, sibling_span, counter)
            if child_node is None:
                return None
        else:
            child_node = _live_node(child)
        node["children"].append(child_node)
    return node


def dump_live_tree(control, sibling_span: int = LIVE_SIBLING_SPAN, child_depth: int = LIVE_CHILD_DEPTH) -> dict:
    """导出以 control 为焦点的实时局部树(深度捕获侧边面板用)。

    结构: 从窗口根到焦点的祖先链, 链上每层附带聚焦子节点前后各 sibling_span 个兄弟,
    焦点节点另展开 child_depth 层子节点。节点总数上限 LIVE_MAX_NODE_COUNT。

    Args:
        control: 鼠标下的 UIA 焦点控件
        sibling_span: 聚焦链每层前后保留的兄弟节点数(建议保持默认)
        child_depth: 焦点节点子树展开深度(child_depth 参数保留供后续调整, 当前取常量)

    Returns:
        树形 dict, 节点含 id/tag_name/cls/name/automation_id/rect/focused/children,
        根节点附 truncated 标记(达上限时为 True)
    """
    if control is None:
        raise Exception("实时树导出失败: 未获取到焦点控件")
    if child_depth < 1:
        child_depth = LIVE_CHILD_DEPTH

    # 祖先链: 焦点 -> ... -> 窗口根(向上回溯, 上限 32 层防环路)
    chain = [control]
    cur = control
    for _ in range(32):
        try:
            parent = cur.GetParent()
        except Exception:
            parent = None
        if parent is None:
            break
        chain.append(parent)
        cur = parent
    chain.reverse()  # 窗口根 -> ... -> 焦点

    counter = [0]
    counter[0] += 1  # 根节点自身
    root = _build_ancestor_level(chain[0], chain, 0, sibling_span, counter)
    if root is None:
        # 极端大树首层即超限: 仅返回聚焦节点自身
        root = _live_node(control, focused=True)
    root["truncated"] = counter[0] >= LIVE_MAX_NODE_COUNT
    logger.debug(f"实时树导出完成: 祖先链 {len(chain)} 层, 共 {counter[0]} 个节点")
    return root
