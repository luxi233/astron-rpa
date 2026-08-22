import asyncio
import json
import queue
import time
import uuid
from enum import Enum
from typing import Any, Optional

import websockets
from astronverse.picker import OperationResult, PickerSign, PickerType, RecordAction, SmartComponentAction, SVCSign
from astronverse.picker.logger import logger
from astronverse.picker.utils.browser import Browser
from pydantic import BaseModel

# 拾取校验(VALIDATE)高亮保持时长(秒), 原为写死 sleep(3)
VALIDATE_HIGHLIGHT_HOLD_SECONDS = 3.0

# L2: 批量校验并发度(定位/截图/CV 匹配逐项耗时秒级, 并行压缩总时长)
BATCH_VALIDATE_MAX_WORKERS = 4


def _validate_one_element(manager: Any, item: dict) -> dict:
    """单元素校验(L2: 线程内执行, report 为局部变量)。

    审计修复(H1): 工作线程触碰 UIA/COM 前须初始化自己的公寓,
    与 recorder_core_win/ws 服务线程的既有约定一致(非 Windows 无 pythoncom 则跳过)。
    返回 {id, name, success, note|error[, cv_candidates]}, 语义与运行时定位一致。
    """
    pythoncom = None
    try:
        import pythoncom  # noqa: PLC0415

        pythoncom.CoInitialize()
    except ImportError:
        pythoncom = None
    try:
        record: dict[str, Any] = {"id": item.get("id", ""), "name": item.get("name", "")}
        try:
            report: dict[str, Any] = {}
            res = manager.locator(item.get("element"), report=report)
            if res is None:
                error_msg = "元素未找到"
                if report.get("cv_ambiguous"):
                    # CV 降级因多候选而中止: 回传候选供前端交互式消歧(I1), 也可重新拾取
                    error_msg += f"(屏幕存在 {report['cv_ambiguous']} 处图像相似命中, 可选定候选或重新拾取)"
                    record["cv_candidates"] = report.get("cv_candidates") or []
                record.update({"success": False, "error": error_msg})
            else:
                notes = []
                if report.get("heal_cache"):
                    notes.append("历史自愈缓存命中")
                elif report.get("healed"):
                    notes.append("已自动修复")
                if report.get("cv_fallback"):
                    notes.append("已降级图像匹配")
                record.update({"success": True, "note": "; ".join(notes)})
        except Exception as e:
            record.update({"success": False, "error": str(e)})
        return record
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def _run_batch_validate(manager: Any, items: list) -> list:
    """L2: 线程池并行逐项校验, map 保序返回与输入一致的结果列表"""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=BATCH_VALIDATE_MAX_WORKERS, thread_name_prefix="batch-validate") as pool:
        return list(pool.map(lambda item: _validate_one_element(manager, item), items))


class PickerRequire(BaseModel):
    """拾取器请求参数模型"""

    pick_sign: PickerSign = PickerSign.START
    pick_type: PickerType = PickerType.ELEMENT
    record_action: Optional[RecordAction] = None  # 仅在RECORD时使用
    smart_component_action: Optional[SmartComponentAction] = None  # 仅在pick_sign是SMART_COMPONENT时使用
    data: str = None
    pick_mode: str = None
    ext_data: dict = {}


class PushAcknowledgment(BaseModel):
    """推送消息确认模型 - 专门用于确认推送消息"""

    message_type: str = "ack"  # 标识这是确认消息
    reply_to: str  # 回复的推送消息ID
    status: str = "success"
    data: str = ""
    err_msg: str = ""


class MessageType(Enum):
    """消息类型：区分响应和推送"""

    RESPONSE = "response"  # 对请求的响应
    PUSH = "push"  # 主动推送


class ResponseKey(Enum):
    """引擎响应消息的key值"""

    SUCCESS = "success"
    ERROR = "error"
    CANCEL = "cancel"
    PING = "ping"


class PushKey(Enum):
    """引擎推送消息的key值"""

    RECORD_START = "record_start"
    RECORD_PAUSE = "record_pause"
    RECORD_AUTOMIC_CHOICE = "record_automic_start"
    RECORD_AUTOMIC_DRAW_END = "record_automic_draw_end"
    PICK_TREE_UPDATE = "pick_tree_update"  # 深度捕获实时控件树(会话内持续推送, 无需ack)


class PickerMessage(BaseModel):
    err_msg: str = ""
    data: str = ""
    key: str
    message_type: Optional[str] = None
    message_id: Optional[str] = None  # 消息唯一ID
    reply_to: Optional[str] = None  # 回复哪个消息的ID

    @classmethod
    def create_response(cls, key: ResponseKey, data: str = "", err_msg: str = ""):
        """创建响应消息"""
        return cls(key=key.value, data=data, err_msg=err_msg)

    @classmethod
    def create_push(cls, key: PushKey, data: str = "", err_msg: str = ""):
        """创建推送消息（带ID）"""
        return cls(
            key=key.value,
            data=data,
            err_msg=err_msg,
            message_type="push",
            message_id=str(uuid.uuid4()),  # 生成唯一ID
        )


class PickerRequestHandler:
    """拾取请求处理器 - 抽离所有业务处理逻辑"""

    def __init__(self, svc):
        self.svc = svc

    async def handle_request(self, ws, input_data: PickerRequire) -> bool:
        """处理拾取请求，返回是否需要关闭连接"""
        logger.info("[RequestHandler] 处理请求: {}".format(input_data))

        if input_data.pick_sign == PickerSign.RECORD:
            await self._handle_record_request(ws, input_data)
            if input_data.record_action == RecordAction.END:
                return True  # 录制end请求不关闭连接
            else:
                return False  # 录制非end请求不关闭连接
        elif input_data.pick_sign == PickerSign.SMART_COMPONENT:
            await self._handle_smart_component_request(ws, input_data)
            return False
        else:
            await self._handle_picker_request(ws, input_data)
            return True  # 其他请求需要关闭连接

    async def _handle_smart_component_request(self, ws, input_data: PickerRequire):
        """处理普通拾取请求"""
        if input_data.smart_component_action == SmartComponentAction.START:
            result = await self._handle_smart_component_start(input_data)
        elif input_data.smart_component_action in [SmartComponentAction.NEXT, SmartComponentAction.PREVIOUS]:
            result = await self._handle_smart_component_next_previous(input_data)
        elif input_data.smart_component_action in [SmartComponentAction.CANCEL, SmartComponentAction.END]:
            result = await self._handle_smart_component_end(input_data)
        else:
            result = OperationResult.error("smart_component_start没有实现").to_dict()

        await self._send_response(ws, result)

    async def _handle_smart_component_start(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取开始"""
        try:
            from astronverse.picker.core.highlight_client import highlight_client

            highlight_client.start_wnd("normal")

            self.svc.tag(SVCSign.SMARTCOMPONENT)
            # 发送拾取开始信号
            res = await self.svc.send_sign(PickerSign.START, input_data.model_dump())

            # high_light.hide_wnd()
            if res == "cancel":
                return OperationResult.cancel().to_dict()
            elif isinstance(res, dict):
                res["picker_type"] = input_data.pick_type.name
                # 拾取成功后，显示透明覆盖窗口阻止对其他区域的操作，直到元素保存
                from astronverse.picker.core.block_overlay import block_overlay

                block_overlay.show()
                return OperationResult.success(data=res).to_dict()
            else:
                return OperationResult.error(res).to_dict()

        except Exception as e:
            logger.error(f"智能组件开始处理失败: {e}")
            return OperationResult.error(str(e)).to_dict()

    async def _handle_smart_component_next_previous(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取开始"""
        try:
            # 发送拾取开始信号
            res = await self.svc.send_sign(PickerSign.SMART_COMPONENT, input_data.model_dump())
            # high_light.hide_wnd()

            if isinstance(res, dict):
                res["picker_type"] = input_data.pick_type.name
                return OperationResult.success(data=res).to_dict()
            else:
                return OperationResult.error(res).to_dict()

        except Exception as e:
            logger.error(f"智能组件拾取处理失败: {e}")
            return OperationResult.error(str(e)).to_dict()

    async def _handle_smart_component_end(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理智能组件拾取结束（保存/取消）"""
        try:
            from astronverse.picker.core.block_overlay import block_overlay
            from astronverse.picker.core.highlight_client import highlight_client

            # 先隐藏覆盖窗口，恢复所有区域的操作
            block_overlay.hide()
            highlight_client.hide_wnd()
            return OperationResult.success(data="").to_dict()
        except Exception as e:
            logger.error(f"智能组件拾取处理失败: {e}")
            return OperationResult.error(str(e)).to_dict()

    async def _handle_record_request(self, ws, input_data: PickerRequire):
        """处理录制请求"""
        from astronverse.picker.core.recorder_core_win import record_manager

        # 委托给录制管理器处理
        result = await record_manager.handle_record_action(input_data.record_action, ws, self.svc, input_data)
        # 发送响应
        await self._send_response(ws, result)

    async def _handle_picker_request(self, ws, input_data: PickerRequire):
        """处理普通拾取请求"""
        if input_data.pick_sign == PickerSign.START:
            result = await self._handle_pick_start(ws, input_data)
        elif input_data.pick_sign == PickerSign.STOP:
            result = await self._handle_pick_stop(input_data)
        elif input_data.pick_sign == PickerSign.VALIDATE:
            result = await self._handle_pick_validate(input_data)
        elif input_data.pick_sign == PickerSign.HIGHLIGHT:
            result = await self._handle_pick_highlight(input_data)
        elif input_data.pick_sign == PickerSign.GAIN:
            result = await self._handle_pick_gain(input_data)
        elif input_data.pick_sign == PickerSign.CONTROL_TREE:
            result = await self._handle_control_tree(input_data)
        elif input_data.pick_sign == PickerSign.VIRTUAL_LIST:
            result = await self._handle_virtual_list(input_data)
        elif input_data.pick_sign == PickerSign.BATCH_VALIDATE:
            result = await self._handle_batch_validate(input_data)
        elif input_data.pick_sign == PickerSign.PICKER_METRICS:
            result = await self._handle_picker_metrics(input_data)
        elif input_data.pick_sign == PickerSign.HEAL_CACHE_DROP:
            result = await self._handle_heal_cache_drop(input_data)
        elif input_data.pick_sign == PickerSign.CV_DISAMBIGUATE:
            result = await self._handle_cv_disambiguate(input_data)
        elif input_data.pick_sign == PickerSign.SWITCH_MODE:
            result = await self._handle_switch_mode(input_data)
        elif input_data.pick_sign == PickerSign.TREE_PICK:
            result = await self._handle_tree_pick(input_data)
        else:
            result = OperationResult.error("pick_sign没有实现").to_dict()

        await self._send_response(ws, result)

    async def _handle_pick_start(self, ws, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取开始"""
        try:
            from astronverse.picker.core.highlight_client import highlight_client

            with highlight_client:
                highlight_client.start_wnd("normal")

                # 处理拾取数据
                if input_data.pick_type in [PickerType.SIMILAR, PickerType.BATCH]:
                    input_data.data = self._process_element_data(input_data)
                    if input_data.pick_mode:
                        input_data.data["pick_mode"] = input_data.pick_mode

                # 深度捕获实时控件树: 注册推送通道并启动推送泵(send_sign 挂起期间
                # 事件循环空闲, 泵协程可并发向同一连接推送; 会话结束后清理)
                deep_tree_task = None
                if input_data.pick_mode in ("DeepUIA", "DeepUIAPick"):
                    self.svc.deep_tree_ws = ws
                    self.svc.deep_tree_queue = queue.Queue(maxsize=4)
                    deep_tree_task = asyncio.create_task(self._deep_tree_pump(ws, self.svc.deep_tree_queue))

                try:
                    # 发送拾取开始信号
                    self.svc.tag(SVCSign.PICKER)
                    res = await self.svc.send_sign(PickerSign.START, input_data.model_dump())
                finally:
                    # 无论结果/异常/超时, 都要摘除推送通道让泵退出
                    self.svc.deep_tree_ws = None
                    self.svc.deep_tree_queue = None
                    if deep_tree_task is not None:
                        try:
                            await asyncio.wait_for(asyncio.shield(deep_tree_task), timeout=1.0)
                        except Exception:
                            deep_tree_task.cancel()
                highlight_client.hide_wnd()

                if res == "cancel":
                    return OperationResult.cancel().to_dict()
                elif isinstance(res, dict):
                    res["picker_type"] = input_data.pick_type.name
                    return OperationResult.success(data=res).to_dict()
                else:
                    return OperationResult.error(res).to_dict()

        except Exception as e:
            logger.error(f"拾取开始处理失败: {e}")
            return OperationResult.error(str(e)).to_dict()

    async def _deep_tree_pump(self, ws, tree_queue) -> None:
        """深度捕获实时树推送泵: 消费绘制线程入队的局部树 JSON, 直接推送到会话连接。

        高频增量数据不走 push_manager 的 ack 跟踪(避免 pending_pushes 无限膨胀);
        连接断开/发送异常即退出泵, 不影响拾取主流程。
        """
        try:
            while self.svc.deep_tree_ws is ws:
                try:
                    payload = tree_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                try:
                    push_msg = PickerMessage.create_push(PushKey.PICK_TREE_UPDATE, data=payload)
                    await ws.send(push_msg.model_dump_json())
                except Exception as e:
                    logger.info(f"实时树推送中断(连接可能已关闭): {e}")
                    break
        finally:
            # 排干残留数据避免脏队列泄漏
            try:
                while not tree_queue.empty():
                    tree_queue.get_nowait()
            except Exception:
                pass

    async def _handle_pick_stop(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取停止"""
        try:
            await self.svc.send_sign(PickerSign.STOP, input_data.model_dump())
            return OperationResult.success().to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_pick_validate(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取校验。

        ext_data.validate_mode(E5): check_position(缺省)/check_click/check_input/check_hover,
        行为模式为非破坏性能力检查, 不真实执行事件。
        """
        try:
            from astronverse.locator.locator import LocatorManager
            from astronverse.picker.core import behavior_check
            from astronverse.picker.core.highlight_client import highlight_client

            mode = (input_data.ext_data or {}).get("validate_mode", behavior_check.VALID_POSITION)

            with highlight_client:
                highlight_client.start_wnd("validate")
                input_data.data = self._process_element_data(input_data)

                # report 回写自愈/CV 降级信息, 校验结果中透传给前端
                report: dict[str, Any] = {}
                res = LocatorManager().locator(input_data.data, report=report)
                if isinstance(res, list):
                    rects = [item.rect() for item in res]
                    match_count = len(res)
                    target = res[0] if res else None
                else:
                    rects = res.rect()
                    match_count = 1
                    target = res

                highlight_client.draw_wnd(rects, "", "validate")
                logger.info(f"拾取校验命中 {match_count} 个元素, 高亮保持 {VALIDATE_HIGHLIGHT_HOLD_SECONDS}s")

                # 自愈提示: 元素原路径失效但已自动修复(建议用户确认后重新拾取)
                heal_note = ""
                if report.get("heal_cache"):
                    heal_note = "原路径失效, 已按历史自愈结果定位, 建议重新拾取"
                elif report.get("healed"):
                    heal_note = (
                        "原路径失效, 已自动修复: " + " → ".join(report.get("relaxations", [])) + ", 建议重新拾取"
                    )
                elif report.get("cv_fallback"):
                    heal_note = "元素定位失败, 已降级为图像匹配定位"

                # E5 行为校验: 高亮后对命中元素做能力检查(不执行事件)
                behavior_note = ""
                if mode != behavior_check.VALID_POSITION:
                    control = target.control() if target is not None else None
                    if control is None:
                        behavior_note = "坐标类定位结果, 行为校验已跳过"
                    else:
                        ok, reason = behavior_check.run_behavior_check(control, mode)
                        if not ok:
                            time.sleep(VALIDATE_HIGHLIGHT_HOLD_SECONDS)
                            return OperationResult.error(f"行为校验未通过: {reason}").to_dict()
                        behavior_note = reason

                # 高亮保持时长参数化(原为写死 sleep(3))
                time.sleep(VALIDATE_HIGHLIGHT_HOLD_SECONDS)

                notes = [note for note in (heal_note, behavior_note) if note]
                suffix = f"({'; '.join(notes)})" if notes else ""
                return OperationResult.success(data=f"校验成功{suffix}").to_dict()

        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_control_tree(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理控件树导出/节点高亮/节点点选拾取请求(E1 控件树浏览器后端能力)。

        ext_data 可选参数:
        - handle: 指定窗口句柄, 缺省时从桌面根控件导出
        - max_depth: 导出深度上限, 缺省 6
        - rect: {left, top, right, bottom}, 指定时仅高亮该区域(树节点点选), 不导出树
        - pick: 窗口层→目标层的节点属性链, 指定时构造 UIA 元素并验证定位(树点选拾取)
        """
        try:
            ext = input_data.ext_data or {}
            pick_chain = ext.get("pick")
            if pick_chain:
                # 树节点点选拾取: 依据属性链构造元素, 定位验证后回传供前端保存
                from astronverse.locator.locator import LocatorManager

                path = [
                    {
                        "tag_name": node.get("tag_name"),
                        "cls": node.get("cls"),
                        "name": node.get("name"),
                        "automation_id": node.get("automation_id"),
                        "checked": True,
                        "disable_keys": [],
                    }
                    for node in pick_chain
                ]
                element = {
                    "app": (pick_chain[0].get("name") or "") if pick_chain else "",
                    "version": "1",
                    "type": "uia",
                    "path": path,
                    "picker_type": "",
                }
                located = False
                try:
                    located = LocatorManager().locator(element, self_heal=False, cv_fallback=False) is not None
                except Exception as e:
                    logger.warning(f"树点选元素验证定位失败: {e}")
                payload = {"element": element, "located": located}
                return OperationResult.success(data=json.dumps(payload, ensure_ascii=False)).to_dict()

            rect = ext.get("rect")
            if rect:
                # 树节点点选高亮: 直接按 rect 绘制, 无需重新定位控件
                from astronverse.picker import Rect
                from astronverse.picker.core.highlight_client import highlight_client

                with highlight_client:
                    highlight_client.start_wnd("validate")
                    highlight_client.draw_wnd(
                        Rect(
                            rect.get("left", 0),
                            rect.get("top", 0),
                            rect.get("right", 0),
                            rect.get("bottom", 0),
                        ),
                        "",
                        "validate",
                    )
                    time.sleep(VALIDATE_HIGHLIGHT_HOLD_SECONDS)
                return OperationResult.success(data="").to_dict()

            import uiautomation as auto

            from astronverse.picker.core.control_tree import DEFAULT_MAX_DEPTH, dump_control_tree

            max_depth = int(ext.get("max_depth", DEFAULT_MAX_DEPTH))
            handle = ext.get("handle")
            root = auto.ControlFromHandle(handle=int(handle)) if handle else auto.GetRootControl()
            tree = dump_control_tree(root, max_depth=max_depth)
            return OperationResult.success(data=json.dumps(tree, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_virtual_list(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理虚拟列表批量采集请求(E4)。

        ext_data 参数:
        - handle: 列表容器窗口句柄(必填)
        - item_tag: 条目控件类型过滤(可选, 如 ListItemControl)
        - item_name: 条目名称过滤(可选, 子串匹配)
        - max_scrolls: 最大滚动次数, 缺省 5
        - horizontal: True 横向滚动采集(表格类横向虚拟化), 缺省纵向
        """
        try:
            import uiautomation as auto

            from astronverse.picker.core.control_tree import dump_control_tree
            from astronverse.picker.core.virtual_list import DEFAULT_MAX_SCROLLS, collect_virtual_list

            ext = input_data.ext_data or {}
            handle = ext.get("handle")
            if not handle:
                return OperationResult.error("VIRTUAL_LIST 缺少容器句柄 handle").to_dict()
            container = auto.ControlFromHandle(handle=int(handle))
            item_tag = ext.get("item_tag")
            item_name = ext.get("item_name")

            def is_item(child) -> bool:
                try:
                    if item_tag and getattr(child, "ControlTypeName", None) != item_tag:
                        return False
                    if item_name and item_name not in (getattr(child, "Name", None) or ""):
                        return False
                    return True
                except Exception:
                    return False

            items = collect_virtual_list(
                container,
                is_item=is_item if (item_tag or item_name) else None,
                max_scrolls=int(ext.get("max_scrolls", DEFAULT_MAX_SCROLLS)),
                horizontal=bool(ext.get("horizontal", False)),
            )
            payload = [dump_control_tree(item, max_depth=1) for item in items]
            return OperationResult.success(data=json.dumps(payload, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_batch_validate(self, input_data: PickerRequire) -> dict[str, Any]:
        """批量校验元素库(发布前体检)。

        data: JSON 数组 [{"id", "name", "element": 元素 json 串或 dict}...]
        返回逐项报告 [{id, name, success, note|error}], 不高亮纯定位检查,
        自愈/CV 降级与运行时行为一致并计入 note。
        """
        try:
            from astronverse.locator.locator import LocatorManager

            items = json.loads(input_data.data) if isinstance(input_data.data, str) else input_data.data
            if not isinstance(items, list):
                return OperationResult.error("BATCH_VALIDATE data 必须为数组").to_dict()

            manager = LocatorManager()
            # L2: 并行校验放到工作线程, 不阻塞 WS 事件循环
            results = await asyncio.to_thread(_run_batch_validate, manager, items)
            passed = sum(1 for r in results if r.get("success"))
            logger.info(f"批量校验完成: {passed}/{len(results)} 通过")
            return OperationResult.success(data=json.dumps(results, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_picker_metrics(self, input_data: PickerRequire) -> dict[str, Any]:
        """拾取可观测性指标查询: 定位/自愈/CV 命中计数与自愈缓存条目"""
        try:
            from astronverse.locator.core import heal_store

            payload = {"metrics": heal_store.metrics_snapshot(), "heal_cache": heal_store.heal_cache_all()}
            return OperationResult.success(data=json.dumps(payload, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_heal_cache_drop(self, input_data: PickerRequire) -> dict[str, Any]:
        """按缓存键删除单条自愈缓存(指标面板手动清理, data 为缓存键)"""
        try:
            from astronverse.locator.core import heal_store

            key = input_data.data if isinstance(input_data.data, str) else str(input_data.data or "")
            dropped = heal_store.heal_cache_drop_key(key)
            return OperationResult.success(data=json.dumps({"key": key, "dropped": dropped})).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_cv_disambiguate(self, input_data: PickerRequire) -> dict[str, Any]:
        """I1 CV 歧义交互式消歧: 用户在候选中选定其一, 按候选区域构造坐标定位器。

        data: JSON {"id", "name", "rect": [l,t,r,b], "score"}; 一次性决策不写自愈缓存。
        """
        try:
            from astronverse.locator.core.cv_fallback import cv_disambiguate

            data = json.loads(input_data.data) if isinstance(input_data.data, str) else (input_data.data or {})
            rect = data.get("rect")
            if not isinstance(rect, list) or len(rect) != 4:
                return OperationResult.error("CV_DISAMBIGUATE rect 必须为 [left,top,right,bottom]").to_dict()
            locator = cv_disambiguate(rect)
            r = locator.rect()
            payload = {
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "success": True,
                "rect": [r.left, r.top, r.right, r.bottom],
                "center": [(r.left + r.right) // 2, (r.top + r.bottom) // 2],
                "score": data.get("score"),
            }
            return OperationResult.success(data=json.dumps(payload, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_switch_mode(self, input_data: PickerRequire) -> dict[str, Any]:
        """I4 会话内捕获模式切换: 就地改写活动会话字典的 pick_mode, 下一绘制周期生效。

        data: 目标模式 'standard'/'deep'/'cv'。标准/深度会话内即时生效;
        CV 需重初始化拾取引擎(requires_reinit=True), 由前端编排退出重进。
        无活动会话时返回错误(无可切换对象)。
        """
        try:
            from astronverse.picker.core.capture_mode import capture_mode_manager

            sign = self.svc.sign()
            if PickerSign.START.value not in sign:
                return OperationResult.error("无进行中的拾取会话, 无法切换捕获模式").to_dict()
            session_data = sign[PickerSign.START.value]
            if not isinstance(session_data, dict):
                return OperationResult.error("会话数据异常, 无法切换捕获模式").to_dict()

            target = input_data.data if isinstance(input_data.data, str) else str(input_data.data or "")
            try:
                result = capture_mode_manager.switch(session_data, target)
            except ValueError as ve:
                return OperationResult.error(str(ve)).to_dict()

            logger.info(
                f"会话内捕获模式切换: {result['previous']} -> {result['mode']} (reinit={result['requires_reinit']})"
            )
            return OperationResult.success(data=json.dumps(result, ensure_ascii=False)).to_dict()
        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_tree_pick(self, input_data: PickerRequire) -> dict[str, Any]:
        """深度捕获实时树节点点选拾取: 按节点属性链构造元素并验证定位。

        data: JSON 属性链(窗口层→目标层, 字段同 CONTROL_TREE pick: tag_name/cls/name/automation_id)。
        定位成功 → 写 TREE_PICK_DONE 信号供绘制主循环消费, 会话以捕获成功结束(与 Ctrl+点击同路径);
        定位失败 → 不结束会话, 回带 located=False 供前端提示换节点重试。
        ack 的 data 为 {tree_pick, located} JSON, 前端据此与真正的捕获结果区分。
        """
        try:
            sign = self.svc.sign()
            if PickerSign.START.value not in sign:
                return OperationResult.error("无进行中的拾取会话, 无法点选树节点").to_dict()

            chain = json.loads(input_data.data) if isinstance(input_data.data, str) else (input_data.data or [])
            if not isinstance(chain, list) or not chain:
                return OperationResult.error("节点属性链为空, 无法点选拾取").to_dict()

            from astronverse.locator.locator import LocatorManager

            path = [
                {
                    "tag_name": node.get("tag_name"),
                    "cls": node.get("cls"),
                    "name": node.get("name"),
                    "automation_id": node.get("automation_id"),
                    "checked": True,
                    "disable_keys": [],
                }
                for node in chain
            ]
            element = {
                "app": (chain[0].get("name") or ""),
                "version": "1",
                "type": "uia",
                "path": path,
                "picker_type": "",
            }
            located = False
            try:
                located = LocatorManager().locator(element, self_heal=False, cv_fallback=False) is not None
            except Exception as e:
                logger.warning(f"树点选元素验证定位失败: {e}")

            if located:
                # 主循环消费信号: 绘制循环下一轮以此为捕获结果结束会话(先于 is_focus 判定)
                sign["TREE_PICK_DONE"] = element
            return OperationResult.success(
                data=json.dumps({"tree_pick": True, "located": located}, ensure_ascii=False)
            ).to_dict()
        except Exception as e:
            logger.error(f"树点选拾取处理失败: {e}")
            return OperationResult.error(str(e)).to_dict()

    async def _handle_pick_highlight(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取高亮"""
        try:
            from astronverse.locator.locator import LocatorManager

            input_data.data = self._process_element_data(input_data)
            data = (
                LocatorManager.parse_element_json(input_data.data)
                if isinstance(input_data.data, str)
                else input_data.data
            )

            Browser.send_browser_extension(
                browser_type=data.get("app"),
                data=data.get("path"),
                key="highLightColumn",
                gate_way_port=self.svc.route_port,
            )

            return OperationResult.success(data="高亮成功").to_dict()

        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    async def _handle_pick_gain(self, input_data: PickerRequire) -> dict[str, Any]:
        """处理拾取获取数据"""
        try:
            from astronverse.locator.locator import LocatorManager
            from astronverse.picker.utils.table_filter import (
                DataFilter,
                table_json_merge_values,
            )

            input_data.data = self._process_element_data(input_data)
            data = (
                LocatorManager.parse_element_json(input_data.data)
                if isinstance(input_data.data, str)
                else input_data.data
            )

            web_info = Browser.send_browser_extension(
                browser_type=data.get("app"),
                data=data.get("path"),
                key="getBatchData",
                gate_way_port=self.svc.route_port,
            )
            values = web_info["values"]
            batch_element = data.get("path")
            batch_element = table_json_merge_values(batch_element, values)
            locate_data = DataFilter(data_json=batch_element).get_filtered_data()

            return OperationResult.success(data=locate_data).to_dict()

        except Exception as e:
            return OperationResult.error(str(e)).to_dict()

    def _process_element_data(self, input_data: PickerRequire):
        """处理元素数据"""
        from astronverse.locator.locator import LocatorManager
        from astronverse.picker.utils.params import complex_param_parser

        global_data = input_data.ext_data.get("global", [])
        data = (
            LocatorManager.parse_element_json(input_data.data) if isinstance(input_data.data, str) else input_data.data
        )
        return complex_param_parser(complex_param=data, global_data=global_data)

    async def _send_response(self, ws, result: dict[str, Any]):
        """发送响应消息"""
        if result.get("success"):
            data = result.get("data", "")
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            elif not isinstance(data, str):
                data = str(data)
            await ws.send(PickerMessage.create_response(ResponseKey.SUCCESS, data=data).model_dump_json())

        else:
            if result.get("cancel"):
                await ws.send(PickerMessage.create_response(ResponseKey.CANCEL).model_dump_json())
            error_msg = result.get("error", "未知错误")
            await ws.send(PickerMessage.create_response(ResponseKey.ERROR, err_msg=error_msg).model_dump_json())


class PushManager:
    """推送管理器 - 处理推送消息的发送和确认"""

    def __init__(self):
        self.pending_pushes = {}  # 存储待确认的推送消息

    async def send_push_message(self, ws, push_key: PushKey, data: str = "") -> str:
        """发送推送消息并记录"""
        push_msg = PickerMessage.create_push(push_key, data=data)

        # 记录待确认的推送
        self.pending_pushes[push_msg.message_id] = {
            "type": push_key.value,
            "timestamp": time.time(),
            "data": push_msg.data,
        }

        await ws.send(push_msg.model_dump_json())
        logger.info(f"推送消息: {push_key.value}, ID: {push_msg.message_id}")

        return push_msg.message_id

    async def handle_acknowledgment(self, ack_data: PushAcknowledgment) -> bool:
        """处理推送确认"""
        reply_to_id = ack_data.reply_to
        status = ack_data.status
        data = ack_data.data

        logger.info(f"[PushManager] 收到推送确认: reply_to={reply_to_id}, status={status}")

        if reply_to_id in self.pending_pushes:
            push_info = self.pending_pushes[reply_to_id]
            logger.info(f"前端确认推送 {push_info['type']}: {data}")
            del self.pending_pushes[reply_to_id]
            return True
        else:
            logger.warning(f"收到未知推送ID的确认: {reply_to_id}")
            return False


class WsServer:
    """WebSocket服务器 - 只负责连接管理和消息路由"""

    def __init__(self, svc, port: int):
        self.svc = svc
        self.port = port

        # 业务处理器
        self.request_handler = PickerRequestHandler(svc)
        self.push_manager = PushManager()

        # 设置录制事件回调
        self._setup_record_callbacks()

    def _setup_record_callbacks(self):
        """设置录制事件回调"""
        from astronverse.picker.core.recorder_core_win import record_manager

        record_manager.set_push_callbacks(
            on_f4=self._on_f4_pressed,
            on_esc=self._on_esc_pressed,
            on_hover=self._on_mouse_hover,
            on_mouse_out=self._on_mouse_out,
        )

    async def _on_f4_pressed(self, ws_connection):
        """录制 F4按键回调"""
        await self.push_manager.send_push_message(ws_connection, PushKey.RECORD_START)

    async def _on_esc_pressed(self, ws_connection):
        """录制 ESC按键回调"""
        await self.push_manager.send_push_message(ws_connection, PushKey.RECORD_PAUSE)

    async def _on_mouse_hover(self, ws_connection, rect_data):
        """录制 鼠标悬停回调"""
        await self.push_manager.send_push_message(
            ws_connection,
            PushKey.RECORD_AUTOMIC_CHOICE,  # 复用现有的信号类型
            data=rect_data,
        )

    async def _on_mouse_out(self, ws_connection):
        """录制 鼠标移出悬停元素区域回调"""
        await self.push_manager.send_push_message(ws_connection, PushKey.RECORD_AUTOMIC_DRAW_END)

    async def websocket_endpoint(self, ws):
        """WebSocket端点 - 只负责消息路由"""
        async for message in ws:
            try:
                data = json.loads(message)

                # 1. 检查是否是推送确认消息
                if data.get("message_type") == "ack":
                    ack_data = PushAcknowledgment(**data)
                    await self.push_manager.handle_acknowledgment(ack_data)
                    continue

                # 2. 检查是否是拾取请求
                if data.get("pick_sign"):
                    input_data = PickerRequire(**data)
                    should_close = await self.request_handler.handle_request(ws, input_data)
                    if should_close:
                        await ws.close()
                    continue

                # 3. 未知消息格式
                logger.warning(f"未知的消息格式: {data}")
                await ws.send(
                    PickerMessage.create_response(ResponseKey.ERROR, err_msg="未知的消息格式").model_dump_json()
                )

            except Exception as e:
                import traceback

                logger.error("WebSocket消息处理错误: {} stack: {}".format(e, traceback.format_exc()))
                try:
                    await ws.send(PickerMessage.create_response(ResponseKey.ERROR, err_msg=str(e)).model_dump_json())
                except:
                    pass  # 连接可能已断开

    def server(self) -> None:
        """启动WebSocket服务器"""
        import pythoncom

        pythoncom.CoInitialize()

        async def start_server():
            """异步启动WebSocket服务器"""
            server = await websockets.serve(
                self.websocket_endpoint,
                "127.0.0.1",
                self.port,
                max_size=10 * 1024 * 1024,
            )
            await server.wait_closed()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(start_server())
        except KeyboardInterrupt:
            logger.info("picker ws接口被中断")
        finally:
            loop.close()
