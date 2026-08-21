import ctypes
import json
import threading
import time
from typing import Optional

from astronverse.picker import (
    DrawResult,
    IElement,
    IPickerCore,
    PickerDomain,
    PickerSign,
    PickerType,
    Point,
    Rect,
    SmartComponentAction,
)
from astronverse.picker.engines.uia_picker import UIAElement, UIAOperate
from astronverse.picker.logger import logger
from astronverse.picker.utils.browser import BrowserControlFinder

# UIPI检测: 目标进程是否管理员(elevated)运行, 带pid缓存避免每轮重复系统调用
_elevated_pid_cache: dict = {}


def _is_process_elevated(process_id: int) -> bool:
    if process_id in _elevated_pid_cache:
        return _elevated_pid_cache[process_id]
    elevated = False
    try:
        import win32api
        import win32con
        import win32security

        h_process = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        try:
            h_token = win32security.OpenProcessToken(h_process, win32con.TOKEN_QUERY)
            try:
                # TokenElevation=20: 返回(TokenElevation结构,) 非零即elevated
                info = win32security.GetTokenInformation(h_token, 20)
                elevated = bool(info[0]) if isinstance(info, (tuple, list)) and len(info) else bool(info)
            finally:
                h_token.Close()
        finally:
            h_process.Close()
    except Exception:
        # 查询失败(权限不足/进程已退出)按非elevated处理, 不影响拾取主流程
        pass
    _elevated_pid_cache[process_id] = elevated
    return elevated


def _is_self_elevated() -> bool:
    return ctypes.windll.shell32.IsUserAnAdmin() != 0


class PickerCore(IPickerCore):
    """拾取的功能集合, 比如鼠标位置，窗口，元素"""

    def __init__(self):
        self.last_point = Point(0, 0)
        self.last_element: Optional[IElement] = None
        self.last_strategy_svc = None
        self.lock = threading.Lock()

        # 保存上一次的有效绘制结果
        self.last_valid_rect: Optional[Rect] = None
        self.last_valid_tag: str = ""
        self.last_valid_domain: Optional[str] = None

        # 深度捕获实时控件树推送: 指纹去重(焦点控件+矩形) + 时间节流
        self._live_tree_fp: Optional[tuple] = None
        self._live_tree_last_ts: float = 0.0

    def _get_element_domain(self, element: IElement) -> str:
        """根据元素类型确定实际使用的 domain"""
        element_type = type(element).__name__
        if element_type == "UIAElement":
            return PickerDomain.UIA.value
        elif element_type == "WEBElement":
            return PickerDomain.WEB.value
        elif element_type == "MSAAElement":
            return PickerDomain.MSAA.value
        else:
            # 默认返回 UIA
            logger.warning(f"无法确定元素类型 {element_type}，使用默认 UIA domain")
            return PickerDomain.UIA.value

    def draw(self, svc, highlight_client, data: dict) -> DrawResult:
        """纯粹的拾取绘制功能，不包含录制相关逻辑"""
        try:
            # 更新鼠标位置
            p_x, p_y = UIAOperate.get_cursor_pos()
            self.last_point.x = p_x
            self.last_point.y = p_y
            pick_type = data.get("pick_type")

            if pick_type == PickerType.POINT:
                # 点拾取不需要绘制，但仍然是成功状态
                return DrawResult(success=True)

            elif pick_type == PickerType.WINDOW:
                return self._draw_window(svc, highlight_client, data)

            elif pick_type in [
                PickerType.ELEMENT,
                PickerType.SIMILAR,
                PickerType.BATCH,
            ]:
                return self._draw_element(svc, highlight_client, data)

            else:
                return DrawResult(success=False, error_message=f"不支持的拾取类型: {pick_type}")

        except Exception as e:
            logger.error(f"拾取绘制失败: {e}")
            return DrawResult(success=False, error_message=str(e))

    def _draw_window(self, svc, highlight_client, data: dict) -> DrawResult:
        """窗口拾取绘制"""
        start_control = UIAOperate.get_windows_by_point(self.last_point)
        result_control = UIAOperate.get_app_windows(start_control)
        if not result_control:
            return DrawResult(success=False, error_message="")
        with self.lock:
            self.last_element = UIAElement(control=result_control)
        process_id = UIAOperate.get_process_id(start_control)
        self.last_strategy_svc = svc.strategy.gen_svc(
            process_id=process_id,
            last_point=self.last_point,
            data=data,
            start_control=start_control,
            domain=PickerDomain.UIA,
        )
        rect = self.last_element.rect()
        tag = self.last_element.tag()
        highlight_client.draw_wnd(rect, msgs=tag)
        return DrawResult(
            success=True,
            rect=rect,
            app=self.last_strategy_svc.app.value,
            domain=PickerDomain.UIA.value,  # 窗口拾取总是使用 UIA
        )

    def _draw_element(self, svc, highlight_client, data: dict) -> DrawResult:
        """元素拾取绘制"""
        # 环境收集
        start_control = UIAOperate.get_windows_by_point(self.last_point)
        if not start_control:
            # 空error_message = 会话保活(不终止拾取): 老旧软件/特殊窗口结构下
            # 起始控件可能暂时拿不到, 若以非空错误返回会立即卸载键鼠钩子结束会话,
            # 用户随后的Ctrl+左键会真实穿透点击到目标应用。此处静默失败等待下一轮重试
            logger.info("拾取预处理 start_control 为空")
            return DrawResult(success=False, error_message="")

        process_id = UIAOperate.get_process_id(start_control)

        # UIPI检测: 目标窗口管理员运行且自身普通权限时, 系统隔离低级钩子——
        # Ctrl+左键会真实穿透点击目标应用(Esc/Ctrl+左键由轮询兜底感知), 画框标签提示用户根因
        if not _is_self_elevated() and _is_process_elevated(process_id):
            uipi_warning = "管理员窗口·点击会穿透(建议以管理员运行设计器)"
            self.last_uipi_warning = uipi_warning
        else:
            self.last_uipi_warning = ""

        # 上下文生成
        if not svc.strategy:
            # 等待策略加载
            timeout = 10  # 10秒超时
            wait_time = 0
            while not svc.strategy and wait_time < timeout:
                time.sleep(0.1)
                wait_time += 0.1

            if not svc.strategy:
                return DrawResult(success=False, error_message="策略加载超时（10s）")

            logger.info("strategy 加载完成")

        domain = PickerDomain.AUTO
        pick_mode = data.get("pick_mode")
        if pick_mode:
            if pick_mode == "WebPick":
                domain = PickerDomain.AUTO_WEB
            elif pick_mode in ("DeepUIA", "DeepUIAPick"):
                # UIA强制深度拾取: 跳过策略试探(JAB/MSAA/SAP), 直达UIA引擎——
                # 对应影刀"深度模式", 用于标准捕获失效的复杂桌面软件
                # (DeepUIAPick为前端原子参数类型名, 透传为pick_mode)
                domain = PickerDomain.UIA
                # 写入 deep 标记使 UIA 遍历以更大深度下钻; 浅拷贝避免污染外部入参 dict
                data = dict(data)
                data["deep"] = True
            else:
                domain = PickerDomain.AUTO_DESK
        self.last_strategy_svc = svc.strategy.gen_svc(
            process_id=process_id, last_point=self.last_point, data=data, start_control=start_control, domain=domain
        )

        # 策略运行
        res = svc.strategy.run(self.last_strategy_svc)
        if not res:
            return DrawResult(success=False, error_message="")

        with self.lock:
            self.last_element = res
        current_rect = self.last_element.rect()
        current_tag = self.last_element.tag()
        # 附加UIPI警示到画框标签(仅管理员目标窗口场景非空)
        if getattr(self, "last_uipi_warning", ""):
            current_tag = "{} [{}]".format(current_tag, self.last_uipi_warning)

        # 确定实际使用的 domain
        actual_domain = self._get_element_domain(self.last_element)

        # 更新缓存
        self.last_valid_rect = current_rect
        self.last_valid_tag = current_tag
        self.last_valid_domain = actual_domain

        # 绘制
        highlight_client.draw_wnd(current_rect, msgs=current_tag)

        # 深度捕获实时控件树: 仅 deep 会话且推送通道已注册时增量推送(失败永不阻断拾取)
        if data.get("deep"):
            self._push_live_tree(svc, self.last_element)

        return DrawResult(
            success=True,
            rect=current_rect,
            app=self.last_strategy_svc.app.value,
            domain=actual_domain,
        )

    def _push_live_tree(self, svc, element) -> None:
        """深度捕获侧边实时树推送: 指纹去重 + 150ms 节流后构树入队。

        推送泵在 ws 事件循环侧消费队列; 本方法任何异常均静默吞掉,
        实时树是增强能力, 不得影响拾取主流程。
        """
        try:
            queue = getattr(svc, "deep_tree_queue", None)
            if queue is None or getattr(svc, "deep_tree_ws", None) is None:
                return
            control = getattr(element, "control", None)
            if control is None:
                return

            # 去重: 焦点控件身份 + 矩形指纹与上次推送一致则跳过
            try:
                fp_id = "-".join(str(x) for x in control.GetRuntimeId())
            except Exception:
                fp_id = str(getattr(control, "NativeWindowHandle", ""))
            rect = element.rect()
            fp = (fp_id, rect.left, rect.top, rect.right, rect.bottom)
            now = time.time()
            # 去重: 焦点未变不重推
            if fp == self._live_tree_fp:
                return
            # 节流: 距上次推送不足 150ms 则跳过(下一轮绘制焦点仍在时会再尝试)
            if now - self._live_tree_last_ts < 0.15:
                return

            from astronverse.picker.core.control_tree import dump_live_tree

            tree = dump_live_tree(control)
            # 非阻塞入队: 推送泵消费不及时则丢弃旧帧(实时树只关心最新状态), 绝不阻塞绘制线程
            try:
                queue.put_nowait(json.dumps(tree, ensure_ascii=False))
            except Exception:
                return
            self._live_tree_fp = fp
            self._live_tree_last_ts = now
        except Exception as e:
            logger.debug(f"实时树推送跳过: {e}")

    def call_pluguin(self, svc, high_light, data: dict):
        """为单独向插件通信定制"""
        import json
        import time

        pick_type = data.get("pick_type", "")
        pick_sign = data.get("pick_sign", "")
        smart_component_action = data.get("smart_component_action", "")
        # time.sleep(5)
        p_x, p_y = UIAOperate.get_cursor_pos()
        cur_point = Point(0, 0)
        cur_point.x = p_x
        cur_point.y = p_y
        # start_control = UIAOperate.get_windows_by_point(cur_point)
        data_str = data.get("data", "{}")
        data_dict = json.loads(data_str) if isinstance(data_str, str) else data_str
        data["data"] = data_dict
        # 然后从解析后的字典中获取值
        app = data_dict.get("app")
        title = data_dict.get("path", {}).get("tabTitle", "")
        parent_control = BrowserControlFinder.get_control_by_app_name(app, title)
        start_control = BrowserControlFinder.get_document_control(parent_control)
        if not start_control:
            logger.info("拾取预处理 start_control 为空")
            return "未找到浏览器，请重试"

        process_id = UIAOperate.get_process_id(start_control)
        if pick_type == PickerType.ELEMENT:
            if pick_sign == PickerSign.SMART_COMPONENT:
                # 上下文生成
                if not svc.strategy:
                    # 等待策略加载
                    timeout = 10  # 10秒超时
                    wait_time = 0
                    while not svc.strategy and wait_time < timeout:
                        time.sleep(0.1)
                        wait_time += 0.1

                    if not svc.strategy:
                        return "策略加载超时（10s）"

                    logger.info("strategy 加载完成")

                cur_strategy_svc = svc.strategy.gen_svc(
                    process_id=process_id,
                    last_point=cur_point,
                    data=data,
                    start_control=start_control,
                    domain=PickerDomain.WEB,
                )

                # 策略运行
                try:
                    res = svc.strategy.run(cur_strategy_svc)
                    if res:
                        cur_rect = res.rect()
                        cur_tag = res.tag()
                        if smart_component_action in [SmartComponentAction.PREVIOUS, SmartComponentAction.NEXT]:
                            high_light.draw_wnd(cur_rect, msgs=cur_tag)
                        return res.path(svc, cur_strategy_svc)
                except Exception as e:
                    logger.info(f"智能组件出现异常 {e}")
                    res = str(e)
                return res

    def element(self, svc, data: dict) -> dict:
        pick_type = data.get("pick_type")
        if pick_type == PickerType.POINT:
            point_data = {"x": self.last_point.x, "y": self.last_point.y}
            return {"point": point_data, "version": "1"}
        elif pick_type == PickerType.WINDOW or pick_type in [PickerType.ELEMENT, PickerType.SIMILAR, PickerType.BATCH]:
            with self.lock:
                if self.last_element:
                    return self.last_element.path(svc, self.last_strategy_svc)
            # 确认拾取时仍无有效元素(如自绘控件无控件树可捕获):
            # 抛出带建议的错误冒泡到前端, 而非静默返回空dict
            raise RuntimeError(
                "未能捕获该位置元素, 该程序可能使用自绘控件(DirectUI/Qt/Flash等)无法暴露控件树。"
                "建议: 1)使用窗口拾取整个窗体; 2)尝试UIA深度拾取; 3)使用CV图像拾取(图像定位)"
            )
        else:
            raise NotImplementedError()
