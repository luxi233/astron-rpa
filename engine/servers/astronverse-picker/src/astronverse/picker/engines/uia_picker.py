import time
from typing import Any, Optional

import pyautogui
import uiautomation as auto
from astronverse.picker import APP, IElement, PickerDomain, PickerType, Point, Rect, BROWSER_UIA_POINT_CLASS
from astronverse.picker.logger import logger
from astronverse.picker.utils.cv import screenshot
from astronverse.picker.utils.process import get_process_name
from astronverse.picker.utils.window import validate_window_rect

element_aliases = {
    "AppBarControl": "应用程序栏",
    "ButtonControl": "按钮",
    "CalendarControl": "日历信息",
    "CheckBoxControl": "复选框",
    "ComboBoxControl": "组合框",
    "CustomControl": "自定义",
    "DataGridControl": "数据网格",
    "DataItemControl": "数据项",
    "DocumentControl": "文档",
    "EditControl": "编辑区",
    "GroupControl": "分组",
    "HeaderControl": "标题栏",
    "HeaderItemControl": "标题项",
    "HyperlinkControl": "超链接",
    "ImageControl": "图像",
    "ListControl": "列表",
    "ListItemControl": "列表项",
    "MenuBarControl": "菜单栏",
    "MenuControl": "菜单",
    "MenuItemControl": "菜单项",
    "PaneControl": "窗格",
    "ProgressBarControl": "进度条",
    "RadioButtonControl": "单选按钮",
    "ScrollBarControl": "滚动条",
    "SemanticZoomControl": "语义缩放",
    "SeparatorControl": "分隔符",
    "SliderControl": "滑块",
    "SpinnerControl": "微调器",
    "SplitButtonControl": "拆分按钮",
    "StatusBarControl": "状态栏",
    "TabControl": "选项卡",
    "TabItemControl": "选项卡项",
    "TableControl": "表格",
    "TextControl": "文本",
    "ThumbControl": "滑块手柄",
    "TitleBarControl": "标题栏",
    "ToolBarControl": "工具栏",
    "ToolTipControl": "工具提示",
    "TreeControl": "树形结构",
    "TreeItemControl": "树形子节点",
    "WindowControl": "窗口",
}


class UIAElement(IElement):
    def __init__(self, control: auto.Control):
        self.control = control
        self.__index = None  # cache index
        self.__rect = None  # cache rect
        self.__tag = None

    def rect(self) -> Rect:
        if self.__rect is None:
            rect = self.control.BoundingRectangle
            self.__rect = Rect(rect.left, rect.top, rect.right, rect.bottom)
            valid_res = True
            is_program_manager = self.control.ClassName == "Progman" and self.control.Name == "Program Manager"
            if is_program_manager:
                valid_res = validate_window_rect(rect.left, rect.top, rect.right, rect.bottom)
            # logger.info(f'UIALocator rect  {valid_res}')
            if not valid_res:
                self.__rect.left = 1
                self.__rect.top = 1
                self.__rect.right = pyautogui.size().width - 1
                self.__rect.bottom = pyautogui.size().height - 1
        return self.__rect

    def index(self) -> int:
        if self.__index is None:
            self.__index = 0
            pre = self.control.GetPreviousSiblingControl()
            while pre:
                self.__index += 1
                pre = pre.GetPreviousSiblingControl()
        return self.__index

    def tag(self) -> str:
        if self.__tag is None:
            tag = self.control.ControlTypeName
            if element_aliases.get(tag):
                tag = element_aliases.get(tag)
            self.__tag = tag
        return self.__tag

    def _is_same_control(self, control1, control2) -> bool:
        """
        判断两个 control 是否是同一个元素
        优先使用 RuntimeId，降级使用其他方法
        """
        try:
            # 方法1: RuntimeId (最可靠，UIA 规范保证唯一性)
            if hasattr(control1, "GetRuntimeId") and hasattr(control2, "GetRuntimeId"):
                rid1 = control1.GetRuntimeId()
                rid2 = control2.GetRuntimeId()
                if rid1 and rid2:
                    return rid1 == rid2
        except Exception:
            pass

        try:
            # 方法2: NativeWindowHandle (次选)
            h1 = getattr(control1, "NativeWindowHandle", None)
            h2 = getattr(control2, "NativeWindowHandle", None)
            if h1 and h2 and h1 != 0 and h2 != 0:
                return h1 == h2
        except Exception:
            pass

        try:
            # 方法3: 属性组合 (兜底)
            rect1 = control1.BoundingRectangle
            rect2 = control2.BoundingRectangle
            return (
                control1.ControlTypeName == control2.ControlTypeName
                and control1.ClassName == control2.ClassName
                and control1.Name == control2.Name
                and rect1.left == rect2.left
                and rect1.top == rect2.top
                and rect1.right == rect2.right
                and rect1.bottom == rect2.bottom
            )
        except Exception:
            return False

    def _has_same_type_sibling(self, parent_control, current_control, tag_name) -> bool:
        try:
            children = parent_control.GetChildren()

            for child in children:
                # 跳过自身
                if self._is_same_control(child, current_control):
                    continue

                # 跳过桌面节点
                try:
                    if UIAOperate._is_desktop_element(child):
                        continue
                except:
                    pass

                # 找到同类型兄弟
                if child.ControlTypeName == tag_name:
                    return True

            return False
        except Exception as e:
            logger.warning(f"快速检查同类型兄弟失败: {e}")
            return True  # 保守策略

    def _get_siblings_by_tag(self, parent_control, current_control, tag_name) -> list:
        try:
            children = parent_control.GetChildren()

            sibling_list = []
            for i, child in enumerate(children):
                # 跳过自身
                if self._is_same_control(child, current_control):
                    continue

                # 跳过桌面节点
                try:
                    if UIAOperate._is_desktop_element(child):
                        continue
                except:
                    pass

                # 只收集同类型的兄弟
                if child.ControlTypeName != tag_name:
                    continue

                try:
                    sibling_value = child.GetValuePattern().Value
                except Exception:
                    sibling_value = None

                sibling_attrs = {
                    "cls": child.ClassName,
                    "name": child.Name,
                    "tag_name": child.ControlTypeName,
                    "value": sibling_value,
                    "index": i,
                }
                try:
                    sibling_automation_id = child.AutomationId
                    if sibling_automation_id and str(sibling_automation_id).strip():
                        sibling_attrs["automation_id"] = sibling_automation_id
                except Exception:
                    pass
                sibling_list.append(sibling_attrs)

            return sibling_list
        except Exception as e:
            logger.warning(f"获取同类型兄弟节点失败: {e}")
            return []

    def _get_empty_attrs(self, current_attrs: dict) -> list:
        """
        获取空值属性列表

        返回：空值属性名列表
        """
        priority_attrs = ["automation_id", "tag_name", "name", "cls", "value", "index"]
        empty_attrs = []
        for attr in priority_attrs:
            attr_value = current_attrs.get(attr)
            # 空字符串、None、空白字符串都视为空值
            if attr_value is None or str(attr_value).strip() == "":
                empty_attrs.append(attr)
        return empty_attrs

    def _calculate_disable_keys_without_siblings(self, current_attrs: dict) -> list:
        """
        计算没有兄弟节点时的 disable_keys（只勾选 tag_name）

        返回：不需要勾选的属性名列表
        """
        priority_attrs = ["automation_id", "tag_name", "name", "cls", "value", "index"]
        empty_attrs = self._get_empty_attrs(current_attrs)

        # tag_name 如果非空，只勾选它；否则抛出异常
        if "tag_name" not in empty_attrs:
            # tag_name 非空，其他全部禁用
            disable_keys = [attr for attr in priority_attrs if attr != "tag_name"]
            return disable_keys
        else:
            # tag_name 为空（不应该出现）
            raise Exception("tag_name 为空，无法唯一识别元素")

    def _calculate_disable_keys_progressive(
        self, current_attrs: dict, parent_control, current_control, is_root_level: bool = False
    ) -> list:
        # automation_id 是 UIA 最稳定的唯一标识, 放在首位优先参与渐进式筛选
        priority_attrs = ["automation_id", "tag_name", "cls", "name", "value", "index"]

        empty_attrs = self._get_empty_attrs(current_attrs)
        available_attrs = [attr for attr in priority_attrs if attr not in empty_attrs]

        logger.info("========== 开始计算 disable_keys ==========")
        logger.info(f"当前元素: {current_attrs}")
        logger.info(f"empty_attrs: {empty_attrs}")
        logger.info(f"available_attrs: {available_attrs}")
        logger.info(f"is_root_level: {is_root_level}")
        logger.info(f"parent_control is None: {parent_control is None}")

        if not available_attrs:
            logger.info("没有可用属性，返回全部禁用")
            return priority_attrs.copy()

        if not parent_control:
            if is_root_level:
                logger.info(f"根节点且无父节点，只禁用空值属性: {empty_attrs}")
                current_attrs.pop("index")
                return []  # empty_attrs.copy()
            else:
                result = self._calculate_disable_keys_without_siblings(current_attrs)
                logger.info(f"无父节点但非根节点，返回: {result}")
                return result

        tag_name = current_attrs.get("tag_name")
        has_same_type = self._has_same_type_sibling(parent_control, current_control, tag_name)
        logger.info(f"has_same_type: {has_same_type}")

        if not has_same_type:
            disable_keys = empty_attrs.copy()
            disable_keys.extend([attr for attr in priority_attrs if attr != "tag_name" and attr not in empty_attrs])
            logger.info(f"没有同类型兄弟，只需 tag_name，disable_keys: {disable_keys}")
            return disable_keys

        sibling_list = self._get_siblings_by_tag(parent_control, current_control, tag_name)
        logger.info(f"获取到 {len(sibling_list)} 个同类型兄弟")

        if not sibling_list:
            disable_keys = empty_attrs.copy()
            disable_keys.extend([attr for attr in priority_attrs if attr != "tag_name" and attr not in empty_attrs])
            logger.info(f"兄弟列表为空，只需 tag_name，disable_keys: {disable_keys}")
            return disable_keys

        for i in range(len(available_attrs)):
            check_attrs = available_attrs[: i + 1]
            logger.info(f"第{i + 1}轮测试: {check_attrs}")

            has_conflict = False
            for sibling in sibling_list:
                all_match = True
                for attr in check_attrs:
                    current_value = str(current_attrs.get(attr, "")).strip()
                    sibling_value = str(sibling.get(attr, "")).strip()
                    if current_value != sibling_value:
                        all_match = False
                        break

                if all_match:
                    logger.info(f"  发现冲突兄弟: name={sibling.get('name')}, cls={sibling.get('cls')}")
                    has_conflict = True
                    break

            if not has_conflict:
                disable_keys = empty_attrs.copy()
                disable_keys.extend(available_attrs[i + 1 :])
                logger.info(f"  找到最小属性集: {check_attrs}")
                logger.info(f"  最终 disable_keys: {disable_keys}")
                return disable_keys

        logger.info(f"所有属性都需要，只禁用空值: {empty_attrs}")
        return empty_attrs

    def path(self, svc=None, strategy_svc=None) -> dict:
        curr_ele = self
        path_list = []
        parent_rects = []
        while True:
            # 添加元素信息到路径列表
            try:
                value = curr_ele.control.GetValuePattern().Value
            except Exception:
                value = None

            # 收集当前元素的所有属性（只添加非空属性）
            current_attrs = {}

            # automation_id (UIA 最稳定的唯一标识, 优先采集)
            try:
                automation_id = curr_ele.control.AutomationId
            except Exception:
                automation_id = None
            if automation_id and str(automation_id).strip():
                current_attrs["automation_id"] = automation_id

            # tag_name
            tag_name = curr_ele.control.ControlTypeName
            if tag_name and str(tag_name).strip():
                current_attrs["tag_name"] = tag_name

            # cls
            cls_name = curr_ele.control.ClassName
            if cls_name and str(cls_name).strip():
                current_attrs["cls"] = cls_name

            # name
            name = curr_ele.control.Name
            current_attrs["name"] = name

            # value
            if value is not None and str(value).strip():
                current_attrs["value"] = value

            # index 总是添加
            current_attrs["index"] = curr_ele.index()

            # 获取父元素
            parent_control = curr_ele.control.GetParentControl()

            # 标记是否是根节点（没有父元素或到达桌面层级）
            is_root_level = False
            if not parent_control:
                # 没有父元素，这是最顶层的节点
                is_root_level = True
                parent = None
            else:
                parent = UIAElement(control=parent_control)
                parent_rects.append(parent.rect())

                # 检查parent是否到达桌面层级
                if UIAOperate._is_desktop_element(parent.control):
                    is_root_level = True

            # === 使用渐进式策略计算 disable_keys ===
            disable_keys = self._calculate_disable_keys_progressive(
                current_attrs, parent_control if not is_root_level else None, curr_ele.control, is_root_level
            )

            current_attrs["checked"] = True
            current_attrs["disable_keys"] = disable_keys
            path_list.append(current_attrs)

            # 如果是根节点，结束循环
            if is_root_level:
                break

            curr_ele = parent

        # 构建返回结果
        path_list.reverse()
        res = {
            "version": "1",
            "type": PickerDomain.UIA.value,
            "app": get_process_name(self.control.ProcessId),
            "path": path_list,
            "img": {
                "self": screenshot(self.rect()),
            },
        }
        pick_type = strategy_svc.data.get("pick_type")
        if pick_type == PickerType.SIMILAR:
            from astronverse.locator.locator import LocatorManager

            similar_path = UIAPicker.get_similar_path(strategy_svc, res)
            if similar_path is None:
                raise Exception("找不到相识元素")
            res["path"] = similar_path
            res["img"]["self"] = strategy_svc.data.get("data", {}).get("img", {}).get("self", "")
            res["picker_type"] = PickerType.SIMILAR.value  # 这个需要在这里提前写好，才能交给locator使用
            similar_list = LocatorManager().locator(res, timeout=10)
            if isinstance(similar_list, list):
                similar_count = len(similar_list)
                if similar_count == 0:
                    raise Exception("找不到相识元素")
            else:
                raise Exception("找不到相识元素")
            res["similar_count"] = similar_count
        return res


class UIAPicker:
    """UIA拾取操作，对uiautomation的封装，

    区别于UIAOperate主要是Operate主要是做前置处理以及其他的先行处理,
    UIAPicker更加针对于拾取本身的能力体现, 且将所有的特殊操作都转换成配置，提供策略使用
    """

    __uia_control_cache__: Optional[UIAElement] = None
    __uia_cache_key__: Optional[tuple] = None  # (root窗口句柄, 进程id), 窗口切换即失效
    __uia_cache_time__: float = 0.0
    UIA_CACHE_TTL = 2.0  # 缓存有效期(秒), 超过后强制重新遍历
    MAX_SEARCH_DEPTH = 40  # 深度遍历上限, 防深树雪崩

    @classmethod
    def _initialize_control(cls, control: auto.Control):
        try:
            # fix: 修复有时候遍历是遍历不下去的，需要获取他的父节点重新向下遍历才行
            # 其中 50026, 50030 分别代表 GroupControl, DocumentControl
            first_child = control.GetFirstChildControl()
            # logger.info(f'测试 __control_init__ {first_child}  {control.ControlType}')
            if not first_child and control.ControlType in [50026, 50030, 50033]:
                while control:
                    control = control.GetParentControl()
        except Exception as e:
            logger.info(f"uia初始化异常 {e}")

    @classmethod
    def _cache_key(cls, control) -> Optional[tuple]:
        """以根窗口句柄+进程id作为缓存失效键"""
        try:
            return (control.NativeWindowHandle, control.ProcessId)
        except Exception:
            return None

    @classmethod
    def _search_elements_recursively(
        cls,
        res_list: list[UIAElement],
        control: auto.Control,
        point: Point,
        ignore_parent_zero=False,
        deep=1,
        max_depth=None,
    ):
        """递归深度遍历"""

        if max_depth is None:
            max_depth = cls.MAX_SEARCH_DEPTH
        if deep > max_depth:
            logger.debug(f"UIA遍历达到深度上限 {max_depth}, 停止下钻")
            return

        if deep == 1 and UIAOperate._is_desktop_element(control):
            # 忽略过多的遍历
            return

        for child in control.GetChildren():
            rect = child.BoundingRectangle

            # 如果在这个范围内就添加进去
            contains = Rect.check_point_containment(rect.left, rect.top, rect.right, rect.bottom, point)
            if contains:
                res_list.append(UIAElement(control=child))

            # 如果忽略parent的面积，可以递归。否则要包含在内才能递归
            if contains:
                cls._search_elements_recursively(res_list, child, point, ignore_parent_zero, deep + 1, max_depth)
            else:
                parent_zero = rect.left == 0 and rect.top == 0 and rect.right == 0 and rect.bottom == 0
                if parent_zero and ignore_parent_zero:
                    cls._search_elements_recursively(res_list, child, point, ignore_parent_zero, deep + 1, max_depth)

    @classmethod
    def get_similar_path(cls, strategy_svc, curr_path):
        """用户给定两个相似元素, 生成泛化路径(对齐影刀宽松语义)。

        判定放宽点:
        - 不再要求两条路径深度完全一致: 公共前缀为共同祖先,
          长路径多出的尾部层全部作为区分层(宽松匹配)
        - 根层(窗口层)不再比较 name(窗口标题): 同应用不同标题的窗口实例
          (如"文档1-Word"/"文档2-Word")也可拾取相似, name 差异通过 disable_keys
          交给定位阶段按窗口类名跨实例匹配
        - 祖先关系(一条路径是另一条的真前缀且无分叉)仍判不相似
        """

        old_ele = strategy_svc.data["data"]
        new_ele = curr_path

        # 过滤
        if old_ele.get("app", "") != new_ele.get("app", ""):
            return None
        if old_ele.get("type", "") != "uia" or new_ele.get("type", "") != "uia":
            return None
        path1 = old_ele.get("path", [])
        path2 = new_ele.get("path", [])
        if not path1 or not path2:
            return None

        match_similar = False
        is_first = True

        def _mark_distinguish(idx: int):
            nonlocal is_first
            if is_first:
                # 第一个区分层只基于 tag_name 做区分
                is_first = False
                path1[idx]["disable_keys"] = ["cls", "name", "value", "index"]
            else:
                # 后续的子节点剔除 name/value 做区分
                path1[idx]["disable_keys"] = ["name", "value"]

        # 根层(窗口层): 只比较 tag_name/cls, name 不参与(窗口标题动态/多实例不同)
        for attr in ["tag_name", "cls"]:
            self_attr = path1[0].get(attr, None)
            other_attr = path2[0].get(attr, None)
            if self_attr and other_attr and self_attr != other_attr:
                return None
        if path1[0].get("name") != path2[0].get("name"):
            # 窗口标题不同 → 定位阶段按窗口类名跨实例匹配, 不按标题锁定单一窗口
            path1[0]["disable_keys"] = ["name"]
        path1[0]["similar_parent"] = True

        # 中间层: 逐层比较公共前缀, 第一个出现属性差异的层即区分层
        common_len = min(len(path1), len(path2))
        for i in range(1, common_len):
            is_eq = True
            attrs = ["tag_name", "cls", "name", "value", "index"]
            for attr in attrs:
                self_attr = path1[i].get(attr, None)
                other_attr = path2[i].get(attr, None)
                if self_attr is not None and other_attr is not None and self_attr != other_attr:
                    is_eq = False
                    break
            if is_eq and not match_similar:
                path1[i]["similar_parent"] = True  # similar_parent 这个值就是标识它的父级
            else:
                match_similar = True
                _mark_distinguish(i)

        # 深度不同时, 参照路径多出的尾部层(公共前缀之外)全部作为区分层
        if len(path1) > common_len:
            if not match_similar:
                # path2 是 path1 的真前缀且无分叉 → 祖先关系, 非相似元素
                return None
            for i in range(common_len, len(path1)):
                _mark_distinguish(i)

        if not match_similar:
            # 完全同路径(同一元素)或 path1 是 path2 的真前缀 → 不构成相似样例
            return None
        return path1

    @classmethod
    def get_element(cls, root: UIAElement, point: Point, **kwargs) -> UIAElement:
        # 获取配置
        used_cache = kwargs.get("used_cache", True)
        root_need_init = kwargs.get("root_need_init", True)
        ignore_parent_zero = kwargs.get("ignore_parent_zero", True)
        # 深度捕获模式可传入更大的遍历深度上限(缺省 MAX_SEARCH_DEPTH)
        max_depth = kwargs.get("max_depth")

        cache_key = cls._cache_key(root.control)

        # 获取上一个缓存: 同一窗口进程且在TTL内且点仍在缓存元素区域内才复用
        if used_cache:
            try:
                res = cls.__uia_control_cache__
                if (
                    res
                    and cache_key is not None
                    and cls.__uia_cache_key__ == cache_key
                    and (time.time() - cls.__uia_cache_time__) <= cls.UIA_CACHE_TTL
                    and res.rect().contains(point)
                ):
                    return res
            except Exception:
                cls.__uia_control_cache__ = None

        # 是否开启root初始化检查
        if root_need_init:
            cls._initialize_control(root.control)

        # 对uia进行深度遍历
        ele_list = [root]
        cls._search_elements_recursively(
            ele_list, root.control, point, ignore_parent_zero=ignore_parent_zero, max_depth=max_depth
        )

        # 获取最小的位置返回
        ele = min(ele_list, key=lambda x: x.rect().area())

        # 回填缓存(窗口句柄+进程id+时间戳失效策略)
        cls.__uia_control_cache__ = ele
        cls.__uia_cache_key__ = cache_key
        cls.__uia_cache_time__ = time.time()
        return ele


class UIAOperate:
    """UIA工具类，对uiautomation的封装"""

    @classmethod
    def _is_desktop_element(cls, control: auto.Control) -> bool:
        """是否是桌面元素对象"""

        if control.ClassName == "#32769":
            return True
        if control.NativeWindowHandle == 0x10010:
            return True
        if control.Name == "桌面 1":
            return True
        return False

    @classmethod
    def _is_window_element(cls, control: auto.Control) -> bool:
        """是否窗口对象"""

        parent = control.GetParentControl()
        if not parent:
            return False
        # 如果他的父级是桌面那么他就是窗口句柄
        return cls._is_desktop_element(parent)

    @classmethod
    def get_cursor_pos(cls) -> tuple[int, int]:
        return auto.GetCursorPos()

    @classmethod
    def get_windows_by_point(cls, point: Point) -> Optional[auto.Control]:
        """
        通过point获取窗口

        特性	    ControlFromPoint	            ControlFromPoint2
        适用场景	需要直接操作具体控件（如按钮、输入框）	仅需窗口级操作（如最小化、关闭）
        """
        try:
            return auto.ControlFromPoint2(point.x, point.y)
        except Exception as e:
            return auto.ControlFromPoint(point.x, point.y)

    @classmethod
    def get_process_id(cls, control: auto.Control) -> int:
        """获取进程名称"""

        return control.ProcessId

    @classmethod
    def get_app_windows(cls, control: Optional[auto.Control]) -> Optional[auto.Control]:
        """ele的根窗口"""

        if not control:
            return None
        parent = control.GetParentControl()
        if not parent:
            return control
        if cls._is_window_element(control):
            return control
        return cls.get_app_windows(parent)

    @classmethod
    def is_control_value_diff_from_web_inject(cls, control: auto.Control):
        try:
            url_win11 = control.GetLegacyIAccessiblePattern().Value  # win11

            target_ctl = control.GetFirstChildControl()  # win10

            url = target_ctl.GetLegacyIAccessiblePattern().Value or url_win11
            # logger.debug(f'获取到的 URL: {url}')

            if not isinstance(url, str) or not url:
                return True  # 不是字符串或为空 走web

            web_matches_schema = {"http", "https", "file", "ftp", "devtools"}

            # 判断 URL 是否以这些 schema 中任意一个开头
            res = any(url.lower().startswith(f"{schema}://") for schema in web_matches_schema)
            # logger.info(f'命中web {res}')
            return res

        except Exception as e:
            logger.info(f"出现异常了: {e}")
            return True

    @classmethod
    def get_web_control(
        cls,
        control: auto.Control,
        app: APP = None,
        point=None,
    ) -> tuple[bool, int, int, Any]:
        x = point.x
        y = point.y
        point_cfg = BROWSER_UIA_POINT_CLASS.get(app.value)
        if not point_cfg:
            return False, 0, 0, 0
        tag_value, tag = point_cfg
        while control:
            if app in [APP.Firefox]:
                # Firefox: 向下遍历子树查找，需要边界判断
                for child, _ in auto.WalkControl(control, includeTop=True, maxDepth=10):
                    if child.AutomationId == tag_value:
                        bound = child.BoundingRectangle
                        if bound.left <= x <= bound.right and bound.top <= y <= bound.bottom:
                            return True, bound.top, bound.left, child.NativeWindowHandle
                        else:
                            return False, 0, 0, 0
            else:
                # 其他浏览器: 向上逐级检查当前控件的 ClassName
                if tag == "ClassName":
                    tag_match = control.ClassName
                elif tag == "AutomationId":
                    tag_match = control.AutomationId
                else:
                    tag_match = ""
                if tag_match == tag_value:
                    bound = control.BoundingRectangle
                    return True, bound.top, bound.left, control.NativeWindowHandle
            control = control.GetParentControl()
        return False, 0, 0, None


uia_picker = UIAPicker()
