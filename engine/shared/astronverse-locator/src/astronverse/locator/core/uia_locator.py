import dataclasses
import re
import time
from copy import deepcopy
from typing import Any, Optional, Union

import pyautogui
from astronverse.baseline.logger.logger import logger
from astronverse.locator import ILocator, PickerType, Rect
from astronverse.locator.utils.window import (
    find_window_by_enum_list,
    find_window_handles_list,
    is_desktop_by_handle,
    show_desktop_rect,
    validate_window_rect,
)
from uiautomation import Control, ControlFromHandle

# 强匹配属性键: automation_id 是 UIA 最稳定的唯一标识, 放在首位优先参与匹配
ATTR_MATCH_KEYS = ["automation_id", "tag_name", "name", "cls", "value"]

# E2 selector 自愈: 渐进放宽阶段定义(每阶段为(描述, 需新增禁用的键列表)),
# 顺序从保守到激进, 窗口层(name)最后放宽, 避免跨窗口误命中
HEAL_STAGES = [
    ("放宽动态属性(name/value)", ["name", "value"]),
    ("放宽类名(cls)", ["cls"]),
    ("仅保留结构(tag_name)", ["automation_id", "index"]),
    ("放宽窗口标题(name@root)", ["name"]),
]

# E2 逐层修复: 针对定位失败层的单步放宽序列(从保守到激进), 最后一步跳层对齐用户手工删层
LAYER_RELAX_STEPS = [
    ("放宽name/value", ["name", "value"]),
    ("放宽cls", ["cls"]),
    ("放宽automation_id/index", ["automation_id", "index"]),
    ("跳层(后代搜索)", None),
]

# 跳层后代搜索的最大深度, 控制遍历成本
DESCENDANT_SEARCH_MAX_DEPTH = 8


class UIALocator(ILocator):
    def __init__(self, control: Control):
        self.__control = control
        self.__rect = None

    def rect(self) -> Optional[Rect]:
        if self.__rect is None:
            rect = self.__control.BoundingRectangle
            logger.info(f"校验结果的初始rect {rect.left} {rect.top} {rect.right} {rect.bottom}")
            is_valid_rect = validate_window_rect(rect.left, rect.top, rect.right, rect.bottom)
            # logger.info(f'UIALocator rect  {is_valid_rect}')
            if not is_valid_rect:
                rect.left = 1 if rect.left < 0 else rect.left
                rect.top = 1 if rect.top < 0 else rect.top
                rect.right = pyautogui.size().width - 1 if rect.right > pyautogui.size().width else rect.right
                rect.bottom = pyautogui.size().height - 1 if rect.bottom > pyautogui.size().height else rect.bottom
            self.__rect = Rect(rect.left, rect.top, rect.right, rect.bottom)
        logger.info(f"校验结果的rect {self.__rect.to_json()}")
        return self.__rect

    def control(self) -> Any:
        return self.__control


@dataclasses.dataclass
class UIANode:
    """这个是前端PATH修改后的值，需要和UIAEle对比"""

    tag_name: str = None  # 标签名
    checked: bool = False  # 是否选中
    disable_keys: list[str] = None  # 禁用的key
    cls: str = None  # class name
    index: int = None  # 索引
    name: str = None
    value: str = None
    automation_id: str = None  # UIA AutomationId
    match_types: dict = None  # 各属性匹配方式: exact/contains/regex, 缺省 exact
    search_descendants: bool = False  # E2自愈跳层: 该层改为在后代中搜索(而非仅直接子控件)


class UIAEle:
    """这个是UIA的值，需要和前端PATH对比, 并记录对比结果"""

    def __init__(self, control: Control, index: int = None, index_match_sort: str = ""):
        # 上面是基于control，和index计算出来的数据
        self.__control = control
        self.__rect = None
        self.__index = index
        self.__cls = None
        self.__name = None
        self.__tag_name = None
        self.__value = None
        self.__automation_id = None

        # 特殊: 这个是相对于UIANode的匹配数据, index的匹配不是强匹配
        self.index_parent_match_sort: str = ""
        # 修复: 构造参数曾被忽略恒为空串, 单层路径排序时 int('') 崩溃
        self.index_match_sort: str = index_match_sort
        # E2自愈: 属性重合度得分(含已禁用键的实际匹配数), 多候选时择优
        self.attr_match_score: int = 0

    @property
    def rect(self):
        if self.__rect is None:
            bounding_rectangle = self.__control.BoundingRectangle
            self.__rect = Rect(
                bounding_rectangle.left,
                bounding_rectangle.top,
                bounding_rectangle.right,
                bounding_rectangle.bottom,
            )
        return self.__rect

    @property
    def tag_name(self):
        if self.__tag_name is None:
            self.__tag_name = self.__control.ControlTypeName
        return self.__tag_name

    @property
    def index(self):
        if self.__index is None:
            self.__index = 0
            pre = self.__control.GetPreviousSiblingControl()
            while pre:
                self.__index += 1
                pre = pre.GetPreviousSiblingControl()
        return self.__index

    @property
    def cls(self):
        if self.__cls is None:
            self.__cls = self.__control.ClassName
        return self.__cls

    @property
    def name(self):
        if self.__name is None:
            self.__name = self.__control.Name
        return self.__name

    @property
    def value(self):
        if self.__value is None:
            try:
                value = self.__control.GetValuePattern().Value
            except Exception:
                value = None
            self.__value = value
        return self.__value

    @property
    def automation_id(self):
        if self.__automation_id is None:
            try:
                self.__automation_id = self.__control.AutomationId
            except Exception:
                self.__automation_id = ""
        return self.__automation_id

    @property
    def control(self):
        return self.__control


class UIAFactory:
    """UIA工厂"""

    @classmethod
    def find(cls, ele: dict, picker_type: str, **kwargs) -> Union[list[UIALocator], UIALocator, None]:
        if picker_type == PickerType.SIMILAR.value:
            return cls.__find_similar__(ele, picker_type, **kwargs)
        else:
            return cls.__find_one__(ele, picker_type, **kwargs)

    # ---------------- E2: selector 自愈 ----------------

    @classmethod
    def _relax_node(cls, node: dict, disable_keys: list) -> bool:
        """对单个路径层追加禁用键, 返回是否有新增放宽"""
        existing = node.setdefault("disable_keys", [])
        changed = False
        for key in disable_keys:
            if key not in existing:
                existing.append(key)
                changed = True
        return changed

    @classmethod
    def _relax_path(cls, path_list: list, disable_keys: list, include_root: bool = False) -> None:
        """对路径各层追加禁用键, 默认不含窗口层(include_root=True 时含, 用于放宽窗口标题)"""
        nodes = path_list if include_root else path_list[1:]
        for node in nodes:
            cls._relax_node(node, disable_keys)

    @classmethod
    def _try_find(cls, ele: dict, picker_type: str, detail: dict, **kwargs):
        """自愈内部定位尝试: 失败时通过 detail 回传失败层级, 异常不向上抛"""
        try:
            return cls.__find_one__(ele, picker_type=picker_type, _heal_detail=detail, **kwargs)
        except Exception as e:
            logger.debug(f"自愈定位失败: {e}")
            return None

    @classmethod
    def heal(cls, ele: dict, picker_type: str, **kwargs) -> dict:
        """selector 自愈, 两阶段策略:

        1. 逐层修复(手术式): 只放宽定位失败的那一层, 依次放宽 name/value → cls →
           automation_id/index → 跳层(后代搜索), 对齐用户手工修改层级的修复方式;
        2. 全局放宽(兜底): 逐层修复无解时按 HEAL_STAGES 对全路径渐进放宽。

        Returns:
            {"locator": ILocator|None, "healed": bool, "relaxations": [描述...],
             "repair_hint": str, "element": 修复后的元素 dict}
        """
        relaxations = []
        relaxed = deepcopy(ele)
        relaxed.setdefault("path", [])
        detail = {}

        # ---- 阶段1: 逐层修复 ----
        path_list = relaxed["path"]
        for _ in range(len(path_list) * len(LAYER_RELAX_STEPS) + 1):
            detail.clear()
            result = cls._try_find(relaxed, picker_type, detail, **kwargs)
            if result is not None:
                return cls._heal_success(relaxations, result, relaxed)
            fail_layer = detail.get("fail_layer")
            # 失败层未知/窗口层失败/路径越界: 逐层修复无从下手, 转全局放宽
            if not fail_layer or fail_layer >= len(path_list):
                break
            node = path_list[fail_layer]
            advanced = False
            for desc, disable_keys in LAYER_RELAX_STEPS:
                if disable_keys is not None:
                    if cls._relax_node(node, disable_keys):
                        relaxations.append(f"第{fail_layer + 1}层{desc}")
                        advanced = True
                        break
                elif not node.get("search_descendants", False):
                    # 跳层: 该层改在后代中搜索, 对齐用户手工删除中间层
                    node["search_descendants"] = True
                    relaxations.append(f"第{fail_layer + 1}层{desc}")
                    advanced = True
                    break
            if not advanced:
                break  # 失败层已全部放宽仍失败, 转全局兜底

        # ---- 阶段2: 全局渐进放宽 ----
        for desc, disable_keys in HEAL_STAGES:
            # 仅"放宽窗口标题"阶段作用于窗口层, 其余阶段不动窗口层避免跨窗口误命中
            include_root = "root" in desc
            cls._relax_path(relaxed["path"], disable_keys, include_root=include_root)
            relaxations.append(desc)
            result = cls._try_find(relaxed, picker_type, detail, **kwargs)
            if result is not None:
                return cls._heal_success(relaxations, result, relaxed)
        return {"locator": None, "healed": False, "relaxations": relaxations, "repair_hint": "", "element": relaxed}

    @classmethod
    def _heal_success(cls, relaxations: list, locator, relaxed: dict) -> dict:
        """组装自愈成功结果(element 为修复后的元素, 供上层缓存持久化)"""
        repair_hint = "元素已通过放宽条件定位: " + " → ".join(relaxations) + "; 建议重新拾取或更新元素属性"
        logger.info(f"selector 自愈成功: {repair_hint}")
        return {
            "locator": locator,
            "healed": True,
            "relaxations": relaxations,
            "repair_hint": repair_hint,
            "element": relaxed,
        }

    @classmethod
    def __get_child_walk_control__(cls, control: Control):
        child = control.GetFirstChildControl()
        index = 0
        while child:
            uia_ele = UIAEle(control=child, index=index)
            yield uia_ele
            index += 1
            child = child.GetNextSiblingControl()

    @classmethod
    def __get_descendant_walk_controls__(cls, control: Control, max_depth: int = DESCENDANT_SEARCH_MAX_DEPTH):
        """BFS 遍历后代控件(E2 自愈跳层), 不含控件自身, 深度受限控制遍历成本"""
        current_level = [control]
        index = 0
        for _ in range(max_depth):
            next_level = []
            for parent in current_level:
                try:
                    child = parent.GetFirstChildControl()
                except Exception:
                    child = None
                while child:
                    yield UIAEle(control=child, index=index)
                    index += 1
                    next_level.append(child)
                    try:
                        child = child.GetNextSiblingControl()
                    except Exception:
                        child = None
            if not next_level:
                break
            current_level = next_level

    @classmethod
    def __attr_overlap_score__(cls, uia_ele: UIAEle, node: UIANode) -> int:
        """属性重合度得分: 节点有值且实际控件匹配上的属性数(含已禁用键), 多候选时择优"""
        score = 0
        for key in ATTR_MATCH_KEYS:
            v1 = getattr(node, key, None)
            if v1 is None:
                continue
            v1 = str(v1)
            v2 = getattr(uia_ele, key, None)
            if v2 is not None:
                v2 = str(v2)
            if not v1 and not v2:
                continue
            match_type = (node.match_types or {}).get(key, "exact")
            if cls.__match_value__(v1, v2, match_type):
                score += 1
        return score

    @classmethod
    def __match_value__(cls, v1, v2, match_type: str) -> bool:
        """按匹配方式比较节点属性值 v1(拾取路径) 与实际控件值 v2"""
        if match_type == "contains":
            return bool(v1) and v1 in v2
        if match_type == "regex":
            try:
                return re.search(v1, v2) is not None
            except re.error:
                logger.warning(f"非法正则, 退化为精确匹配: {v1}")
                return v1 == v2
        return v1 == v2

    @classmethod
    def __compare_node_and_uia_ele__(cls, uia_ele: UIAEle, node: UIANode, keys: list[str]) -> bool:
        # 忽略没有选中
        if not node.checked:
            return True

        for key in keys:
            if key in node.disable_keys:
                continue
            v1 = getattr(node, key, None)
            v2 = getattr(uia_ele, key, None)
            # 路径未采集 automation_id(如旧版本拾取数据)时不作为约束条件
            if v1 is None and key == "automation_id":
                continue
            if v1 is not None:
                v1 = str(v1)
            if v2 is not None:
                v2 = str(v2)
            if not v1 and not v2:
                continue
            match_type = (node.match_types or {}).get(key, "exact")
            if not cls.__match_value__(v1, v2, match_type):
                return False
        return True

    @classmethod
    def __show_desktop_ele__(cls, root_handle, root_ctrl, rect):
        # 如果是桌面元素，将遮挡的窗口最小化
        if not root_handle or not root_ctrl:
            return
        if is_desktop_by_handle(root_handle, root_ctrl):
            show_desktop_rect(rect, desktop_handle=root_handle)
            time.sleep(0.2)

    @classmethod
    def _format_node_info(cls, node_or_obj) -> str:
        """格式化节点信息为单行字符串"""
        attrs = []
        for key in ["automation_id", "tag_name", "name", "cls", "value"]:
            value = getattr(node_or_obj, key, None)
            if value:  # 只显示有值的属性
                attrs.append(f"{key}={value}")
        return ", ".join(attrs)

    @classmethod
    def __find_similar__(cls, ele: dict, picker_type: str, **kwarg) -> Union[list[UIALocator], None]:
        path_list = ele.get("path", [])
        if not path_list:
            return None

        # 1. 先定位父路径(similar_parent共同祖先层); 失败时逐层截短父路径降级重试,
        #    被截短的层前插到区分链头部做结构化匹配(tag+cls):
        #    否则截掉List后, ListItem会被当成Pane的直接子级匹配, 层级错位必然匹配为空
        parent_path = [v for v in path_list if v.get("similar_parent", False)]
        distinguish_path = [v for v in path_list if not v.get("similar_parent", None)]
        if not distinguish_path:
            return None

        parent_locator = None
        while parent_path:
            locate_ele = deepcopy(ele)
            locate_ele["path"] = deepcopy(parent_path)
            try:
                parent_locator = cls.__find_one__(locate_ele, picker_type=picker_type, **kwarg)
            except Exception as e:
                logger.debug(f"父路径定位失败(剩余{len(parent_path)}层): {e}")
                parent_locator = None
            if parent_locator:
                break
            drop = deepcopy(parent_path.pop())
            drop.pop("similar_parent", None)
            drop["disable_keys"] = ["name", "value", "index"]  # 结构化匹配: 仅tag+cls
            drop["similar_fallback"] = True  # 标记为降级结构层(路径层), 不作为枚举层
            distinguish_path.insert(0, drop)
        if not parent_locator:
            raise Exception("元素无法找到")
        assert isinstance(parent_locator.control(), Control)

        # 2. 再找子元素
        #    区分链分两类: 降级结构层(前缀, 仅作路径下钻且保留全部分支) + 原区分层(首层枚举相似项, 后续层链内择优)
        res = []

        def _to_uianode(path: dict) -> UIANode:
            return UIANode(
                tag_name=path.get("tag_name", None),
                checked=path.get("checked", None),
                disable_keys=path.get("disable_keys", []),
                cls=path.get("cls", None),
                index=path.get("index", None),
                name=path.get("name", None),
                value=path.get("value", None),
                automation_id=path.get("automation_id", None),
                match_types=path.get("match_types", None),
            )

        # 2.1 降级结构层逐层下钻(全部分支保留, 容错同tag+cls多容器)
        eff_parents = [parent_locator.control()]
        for fb in [n for n in distinguish_path if n.get("similar_fallback")]:
            fb_node = _to_uianode(fb)
            nxt = []
            for ctrl in eff_parents:
                for child in cls.__get_child_walk_control__(ctrl):
                    child_ele = UIAEle(control=child.control, index=0, index_match_sort="1")
                    if cls.__compare_node_and_uia_ele__(child_ele, fb_node, ATTR_MATCH_KEYS):
                        nxt.append(child.control)
            eff_parents = nxt
            if not eff_parents:
                return res
        node_list = [_to_uianode(p) for p in distinguish_path if not p.get("similar_fallback")]

        # 2.2 原区分层匹配: 首层枚举, 后续层择优
        for eff_root in eff_parents:
            for root_ctrl in cls.__get_child_walk_control__(eff_root):
                # 判断第一层子元素是否符合规范
                root_ele = UIAEle(control=root_ctrl.control, index=0, index_match_sort="1")
                is_ok = cls.__compare_node_and_uia_ele__(root_ele, node_list[0], ATTR_MATCH_KEYS)
                if not is_ok:
                    continue

                if len(node_list) == 1:
                    # 如果只有一层就直接结束
                    res.append(UIALocator(control=root_ctrl.control))
                    continue
                else:
                    # 如果还有多层就需要向下遍历，并找到一个相近的值
                    search_list = [UIAEle(control=root_ctrl.control, index=0, index_match_sort="1")]
                    i = 0
                    for i, node in enumerate(node_list[1:]):
                        # i 表示第几层

                        # 4.1 遍历查询里面的子集
                        child_list = []
                        for search in search_list:
                            for uia_ele in cls.__get_child_walk_control__(search.control):
                                uia_ele.index_parent_match_sort = search.index_match_sort
                                child_list.append(uia_ele)

                        # 4.2 基于前端传递的node, 过滤掉不符合要求的, 强匹配
                        child_list = [
                            item for item in child_list if cls.__compare_node_and_uia_ele__(item, node, ATTR_MATCH_KEYS)
                        ]

                        # 4.3 基于前端传递的node, 处理index，弱匹配
                        for item in child_list:
                            index_match = cls.__compare_node_and_uia_ele__(item, node, ["index"])
                            item.index_match_sort = "{}{}".format(
                                item.index_parent_match_sort, "1" if index_match else "0"
                            )

                        # 4.4 去下一层又去做比较，直到没有找到任何符合，或者层级结束
                        search_list = child_list
                        if not search_list:
                            break

                    if not search_list or i != (len(node_list) - 2):
                        continue
                    search_list.sort(key=lambda s: -int(s.index_match_sort))
                    match = search_list[0]
                    res.append(UIALocator(control=match.control))
        return res

    @classmethod
    def __find_one__(cls, ele: dict, picker_type: str, _heal_detail: dict = None, **kwargs) -> Union[UIALocator, None]:
        """
        使用列表遍历的方式查找窗口句柄，当找到元素时停止遍历
        使用 find_window_by_enum_list 和 find_window_handles_list 获取句柄列表

        _heal_detail: 自愈内部传入的可变字典, 失败时回写 fail_layer 供逐层修复定位失败层
        """
        app_name = ele.get("app", "")
        path_list = ele.get("path", [])
        if not path_list:
            return None

        # 1. 处理前端path
        node_list = [
            UIANode(
                tag_name=path.get("tag_name", None),
                checked=path.get("checked", None),
                disable_keys=path.get("disable_keys", []),
                cls=path.get("cls", None),
                index=path.get("index", None),
                name=path.get("name", None),
                value=path.get("value", None),
                automation_id=path.get("automation_id", None),
                match_types=path.get("match_types", None),
                search_descendants=path.get("search_descendants", False),
            )
            for path in path_list
        ]

        first_cls = node_list[0].cls if "cls" not in node_list[0].disable_keys else None
        first_name = node_list[0].name if "name" not in node_list[0].disable_keys else None
        first_app_name = app_name if app_name not in node_list[0].disable_keys else None

        # 2. 获取所有可能的窗口句柄
        root_handles = []

        # 再尝试使用 find_window_handles_list 获取句柄列表
        try:
            handles_list = find_window_handles_list(
                first_cls, first_name, app_name=first_app_name, picker_type=picker_type
            )
            if handles_list:
                root_handles.extend(handles_list)
        except Exception as e:
            logger.debug(f"find_window_handles_list 调用失败: {e}")
        if len(root_handles) == 0:
            # 先尝试使用 find_window_by_enum_list 获取句柄列表
            try:
                enum_handles = find_window_by_enum_list(
                    first_cls,
                    first_name,
                    app_name=first_app_name,
                    picker_type=picker_type,
                )
                if enum_handles:
                    root_handles.extend(enum_handles)
            except Exception as e:
                logger.debug(f"find_window_by_enum_list 调用失败: {e}")

        # 去重处理
        root_handles = list(set(root_handles))

        if not root_handles:
            if _heal_detail is not None:
                _heal_detail["fail_layer"] = 0  # 窗口层未命中
            raise Exception("元素无法找到")

        logger.info(f"找到 {len(root_handles)} 个窗口句柄，开始遍历查找")

        # 3. 遍历所有句柄，尝试找到元素
        for idx, root_handle in enumerate(root_handles):
            try:
                logger.debug(f"正在尝试第 {idx + 1} 个句柄: {root_handle}")
                root_ctrl = ControlFromHandle(handle=root_handle)
                # 定位链路不再置顶窗口, 避免改变用户前台窗口焦点(原 top_window 副作用)

                # 4. 如果业务类型 WINDOW, 就直接结束
                if picker_type == PickerType.WINDOW.value:
                    logger.info(f"找到WINDOW类型元素，使用句柄: {root_handle}")
                    return UIALocator(control=root_ctrl)

                # 5. 忽略index的一层一层查找
                search_list = [UIAEle(control=root_ctrl, index=0, index_match_sort="1")]
                i = 0
                element_found = True  # 标记是否找到元素

                for i, node in enumerate(node_list[1:]):
                    # 5.1 遍历查询里面的子集; E2自愈跳层时改在后代中搜索(对齐用户手工删层)
                    child_list = []
                    tag_list = []
                    walk_fn = (
                        cls.__get_descendant_walk_controls__
                        if node.search_descendants
                        else cls.__get_child_walk_control__
                    )
                    for search in search_list:
                        for uia_ele in walk_fn(search.control):
                            uia_ele.index_parent_match_sort = search.index_match_sort
                            child_list.append(uia_ele)
                            tag_list.append(uia_ele.tag_name)

                    # logger.debug(f"拾取节点: {cls._format_node_info(node)}")
                    # for idx_child, ni in enumerate(child_list):
                    #     logger.debug(f"  节点{idx_child}: {cls._format_node_info(ni)}")

                    # 5.2 基于前端传递的node, 过滤掉不符合要求的, 强匹配
                    befor_cmp_child = child_list
                    child_list = [
                        item for item in child_list if cls.__compare_node_and_uia_ele__(item, node, ATTR_MATCH_KEYS)
                    ]
                    # if len(child_list) > 0:
                    #     logger.info(f'筛选完是{child_list[0].tag_name}')

                    # 5.3 基于前端传递的node, 处理index，弱匹配; 并记录属性重合度供多候选择优
                    for item in child_list:
                        index_match = cls.__compare_node_and_uia_ele__(item, node, ["index"])
                        item.index_match_sort = "{}{}".format(item.index_parent_match_sort, "1" if index_match else "0")
                        item.attr_match_score = cls.__attr_overlap_score__(item, node)

                    # 5.4 去一下层又去做比较，直到没有找到任何符合，或者层级结束
                    search_list = child_list
                    if not search_list:
                        logger.debug(f"筛选完后剩余child_list为空 当前层级是{i} 候选taglist是 {tag_list}")
                        logger.debug(f"筛选前候选节点({len(befor_cmp_child)}个):")
                        for idx_child, ni in enumerate(befor_cmp_child):
                            logger.debug(f"  节点{idx_child}: {cls._format_node_info(ni)}")
                        logger.debug(f"拾取节点: {cls._format_node_info(node)}")
                        element_found = False
                        if _heal_detail is not None:
                            _heal_detail["fail_layer"] = i + 1  # node_list 中的实际层级(0为窗口层)
                        break

                # 6. 检查是否成功找到元素
                # 单层路径(仅窗口层): 相似元素父路径截短降级的兜底场景, 直接返回窗口控件
                # (否则 i==len(node_list)-2 即 0==-1 恒为False, 窗口层永远定位失败)
                if element_found and search_list and (len(node_list) == 1 or i == (len(node_list) - 2)):
                    # 7. 处理index: 属性重合度高者优先(自愈放宽后多候选时避免误命中), 其次 index 匹配度
                    search_list.sort(key=lambda s: (-(getattr(s, "attr_match_score", 0)), -int(s.index_match_sort)))
                    match = search_list[0]

                    # 8. 后处理
                    # 显示桌面元素，遮挡的都隐藏掉
                    cls.__show_desktop_ele__(root_handle, root_ctrl, match.rect)
                    res = UIALocator(control=match.control)
                    logger.info(f"成功找到元素，使用句柄: {root_handle}，校验结果的rect {res.rect().to_json()}")
                    return res
                else:
                    logger.debug(f"句柄 {root_handle} 未找到匹配元素，继续尝试下一个")

            except Exception as e:
                # 如果当前句柄处理失败，继续尝试下一个句柄
                logger.debug(f"处理句柄 {root_handle} 时出错: {e}")
                continue

        # 如果所有句柄都无法找到元素，抛出异常
        logger.error(f"遍历了 {len(root_handles)} 个句柄，均未找到匹配元素")
        raise Exception("元素无法找到")

    @classmethod
    def __find_partial_match__(cls, ele: dict, picker_type: str, **kwargs) -> Union[UIALocator, None]:
        """
        根据路径查找元素，如果路径没有完全匹配，返回最后匹配的元素而不是报错
        """
        logger.info(f"UIAFactory __find_partial_match__ 开始查找元素 {ele}")
        app_name = ele.get("app", "")
        path_list = ele.get("path", [])
        if not path_list:
            return None

        # 1. 处理前端path
        node_list = [
            UIANode(
                tag_name=path.get("tag_name", None),
                checked=path.get("checked", None),
                disable_keys=path.get("disable_keys", []),
                cls=path.get("cls", None),
                index=path.get("index", None),
                name=path.get("name", None),
                value=path.get("value", None),
                automation_id=path.get("automation_id", None),
                match_types=path.get("match_types", None),
            )
            for path in path_list
        ]

        first_cls = node_list[0].cls if node_list[0].cls not in node_list[0].disable_keys else None
        first_name = node_list[0].name if node_list[0].name not in node_list[0].disable_keys else None
        first_app_name = app_name if app_name not in node_list[0].disable_keys else None

        # 2. 获取所有可能的窗口句柄
        root_handles = []

        # 再尝试使用 find_window_handles_list 获取句柄列表
        try:
            handles_list = find_window_handles_list(first_cls, first_name, app_name=first_app_name)
            if handles_list:
                root_handles.extend(handles_list)
        except Exception as e:
            logger.debug(f"find_window_handles_list 调用失败: {e}")
        if len(root_handles) == 0:
            # 先尝试使用 find_window_by_enum_list 获取句柄列表
            try:
                enum_handles = find_window_by_enum_list(first_cls, first_name, app_name=first_app_name)
                if enum_handles:
                    root_handles.extend(enum_handles)
            except Exception as e:
                logger.debug(f"find_window_by_enum_list 调用失败: {e}")

        # 去重处理
        root_handles = list(set(root_handles))

        if not root_handles:
            raise Exception("元素无法找到")

        logger.info(f"找到 {len(root_handles)} 个窗口句柄，开始遍历查找")

        # 3. 遍历所有句柄，尝试找到元素
        best_match = None
        best_match_depth = -1

        for idx, root_handle in enumerate(root_handles):
            try:
                logger.debug(f"正在尝试第 {idx + 1} 个句柄: {root_handle}")
                root_ctrl = ControlFromHandle(handle=root_handle)
                # 定位链路不再置顶窗口, 避免改变用户前台窗口焦点(原 top_window 副作用)

                # 5. 忽略index的一层一层查找
                search_list = [UIAEle(control=root_ctrl, index=0, index_match_sort="1")]
                # 根元素已经匹配了第一个节点，所以初始深度为1
                current_depth = 1
                last_valid_match = search_list[0]  # 根元素作为初始匹配

                for i, node in enumerate(node_list[1:]):
                    # 5.1 遍历查询里面的子集
                    child_list = []
                    tag_list = []
                    for search in search_list:
                        for uia_ele in cls.__get_child_walk_control__(search.control):
                            uia_ele.index_parent_match_sort = search.index_match_sort
                            child_list.append(uia_ele)
                            tag_list.append(uia_ele.tag_name)

                    # 5.2 基于前端传递的node, 过滤掉不符合要求的, 强匹配
                    befor_cmp_child = child_list
                    child_list = [
                        item for item in child_list if cls.__compare_node_and_uia_ele__(item, node, ATTR_MATCH_KEYS)
                    ]

                    # 5.3 基于前端传递的node, 处理index，弱匹配
                    for item in child_list:
                        index_match = cls.__compare_node_and_uia_ele__(item, node, ["index"])
                        item.index_match_sort = "{}{}".format(item.index_parent_match_sort, "1" if index_match else "0")

                    # 5.4 如果找到了匹配的子元素，更新search_list和当前匹配深度
                    if child_list:
                        search_list = child_list
                        current_depth = i + 2  # i是从0开始的，加上根元素的1，所以是i+2
                        # 保存当前层级的最佳匹配
                        search_list.sort(key=lambda s: -int(s.index_match_sort))
                        last_valid_match = search_list[0]
                    else:
                        # 当前层级没有匹配，停止搜索
                        logger.debug(f"筛选完后剩余child_list为空 当前层级是{i} 候选taglist是 {tag_list}")
                        logger.debug(f"筛选前候选节点({len(befor_cmp_child)}个):")
                        for idx_child, ni in enumerate(befor_cmp_child):
                            logger.debug(f"  节点{idx_child}: {cls._format_node_info(ni)}")
                        logger.debug(f"拾取节点: {cls._format_node_info(node)}")
                        break

                # 6. 判断是否找到了更好的匹配
                if current_depth > best_match_depth:
                    best_match_depth = current_depth
                    if current_depth == len(node_list):
                        # 完全匹配，直接返回
                        cls.__show_desktop_ele__(root_handle, root_ctrl, last_valid_match.rect)
                        res = UIALocator(control=last_valid_match.control)
                        logger.info(f"完全匹配成功，使用句柄: {root_handle}，校验结果的rect {res.rect().to_json()}")
                        return res
                    else:
                        # 部分匹配，保存最佳匹配
                        best_match = (root_handle, root_ctrl, last_valid_match)
                        logger.debug(f"句柄 {root_handle} 部分匹配，深度: {current_depth}")

            except Exception as e:
                # 如果当前句柄处理失败，继续尝试下一个句柄
                logger.debug(f"处理句柄 {root_handle} 时出错: {e}")
                continue

        # 7. 返回最佳匹配结果
        if best_match:
            root_handle, root_ctrl, match_ele = best_match
            cls.__show_desktop_ele__(root_handle, root_ctrl, match_ele.rect)
            res = UIALocator(control=match_ele.control)
            logger.info(
                f"部分匹配成功，使用句柄: {root_handle}，匹配深度: {best_match_depth}，校验结果的rect {res.rect().to_json()}"
            )
            return res
        else:
            logger.error(f"遍历了 {len(root_handles)} 个句柄，均未找到任何匹配元素")
            raise Exception("元素无法找到")


uia_factory = UIAFactory()
