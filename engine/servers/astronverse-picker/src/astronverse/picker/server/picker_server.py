import json
import queue
import time
import traceback

from astronverse.picker import DrawResult, PickerSign, SVCSign
from astronverse.picker.core.highlight_client import highlight_client
from astronverse.picker.logger import logger


class PickerServer:
    def __init__(self, service_context):
        self.service_context = service_context
        self.start_time = None  # 用于统计是否卡顿
        self.end_time = None  # 用于统计是否卡顿

    def server(self):
        """
        处理ws_server发过来的消息，串联画框，事件监听，还有拾取核心 pick_core
        后续正常情况下无需修改该部分代码
        """
        while True:
            # 等待加载完成
            if not self.service_context.event_core:
                time.sleep(0.1)
                continue
            if not self.service_context.picker_core:
                time.sleep(0.1)
                continue

            # 外部消息处理
            sign = self.service_context.sign()
            if PickerSign.STOP.value in sign:
                try:
                    # 退出

                    # 1.隐藏画框
                    highlight_client.hide_wnd()
                    time.sleep(0.1)  # 等待画框真正隐藏

                    # 收集返回数据
                    result = None
                except Exception as e:
                    logger.error("pick error: {} {}".format(e, traceback.format_exc()))
                    result = "{}".format(e)
                finally:
                    # 2.退出事件监听
                    self.service_context.event_core.close()

                # 3.消费STOP消息,给前端
                del sign[PickerSign.STOP.value]
                result_sign = "{}_RES".format(PickerSign.STOP.value)
                sign[result_sign] = result

                logger.info("拾取结束，外部退出")
            elif PickerSign.START.value in sign:
                try:
                    # 启动事件监听
                    is_start = self.service_context.event_core.start()
                    if is_start:
                        logger.info("拾取开始")
                    event_core = self.service_context.event_core
                    # 轮询兜底: UIPI(管理员目标窗口)隔离钩子时, 钩子回调不触发,
                    # 用GetAsyncKeyState轮询感知Esc/Ctrl+左键(详见poll_fallback注释)
                    event_core.poll_fallback()
                    picker_data = sign[PickerSign.START.value]
                    # 深度捕获会话: Ctrl+左键不结束会话, 而是 toggle 实时树固定/解冻
                    # (固定后用户可从容在面板树上浏览点选, 树不随鼠标刷新)
                    deep_session = isinstance(picker_data, dict) and picker_data.get("pick_mode") in (
                        "DeepUIA",
                        "DeepUIAPick",
                    )
                    if (
                        event_core.is_cancel()
                        or "TREE_PICK_DONE" in sign
                        or (event_core.is_focus() and not deep_session)
                    ):
                        # 退出

                        try:
                            # 1.隐藏画框
                            # highlight_client.hide_wnd()
                            # time.sleep(0.1)  # 等待画框真正隐藏
                            if (
                                event_core.is_cancel()
                                or (event_core.is_focus() and self.service_context.event_tag == SVCSign.PICKER)
                                or "TREE_PICK_DONE" in sign
                            ):
                                highlight_client.hide_wnd()
                                time.sleep(0.1)

                            # 收集返回数据
                            if "TREE_PICK_DONE" in sign:
                                # 深度捕获树节点点选: ws 侧已构造元素并验证定位,
                                # 直接以捕获成功结束会话(与 Ctrl+点击同路径回传)
                                result = sign["TREE_PICK_DONE"]
                                del sign["TREE_PICK_DONE"]
                            elif self.service_context.event_core.is_focus():
                                picker_data = sign[PickerSign.START.value]
                                result = self.service_context.picker_core.element(self.service_context, picker_data)
                            else:
                                result = "cancel"
                        except Exception as e:
                            logger.error("pick error: %s %s", e, traceback.format_exc())
                            result = "{}".format(e)
                        finally:
                            # 2.退出事件监听
                            self.service_context.event_core.close()

                        # 3.消费Cancel或者focus消息,给前端
                        del sign[PickerSign.START.value]
                        result_sign = "{}_RES".format(PickerSign.START.value)
                        sign[result_sign] = result

                        logger.info("拾取结束，主动退出")
                    elif event_core.is_focus() and deep_session:
                        # 深度捕获 Ctrl+左键: toggle 实时树固定/解冻, 不结束会话。
                        # 面板树上从容浏览/点选必须先固定(鼠标一移树就刷新); 冻结时
                        # 绘制循环继续(画框跟随), 仅停止树推送(_push_live_tree 短路)。
                        # 消费后重置标志, 否则下一轮主循环会重复 toggle。
                        frozen = not getattr(self.service_context, "deep_tree_frozen", False)
                        self.service_context.deep_tree_frozen = frozen
                        logger.info(f"深度捕获实时树{'固定(树不随鼠标刷新)' if frozen else '恢复跟随'}")
                        try:
                            tree_queue = self.service_context.deep_tree_queue
                            if tree_queue is not None:
                                payload = json.dumps({"frozen": frozen})
                                try:
                                    tree_queue.put_nowait(payload)
                                except queue.Full:
                                    # 状态帧必达: 队满先丢最旧树帧(树帧可丢, 前端指纹去重下损失最小),
                                    # 否则冻结/解冻提示丢失会造成面板与实际状态短暂不一致
                                    try:
                                        tree_queue.get_nowait()
                                    except queue.Empty:
                                        pass
                                    tree_queue.put_nowait(payload)
                        except Exception as e:
                            logger.debug(f"树固定状态推送跳过: {e}")
                        event_core.reset_focus_flag()
                    else:
                        # 绘图
                        self.start_time = time.time()
                        draw_result: DrawResult = self.service_context.picker_core.draw(
                            self.service_context,
                            highlight_client,
                            sign[PickerSign.START.value],
                        )
                        self.end_time = time.time()
                        # 节流: 绘图轮询间留出空档, 避免失败路径(如老软件UIA持续失败)下
                        # 无间歇空转独占GIL, 导致键鼠钩子线程响应延迟
                        time.sleep(0.03)

                        # 检查绘图结果
                        if not draw_result.success and draw_result.error_message:
                            logger.warning(f"拾取绘图失败: {draw_result.error_message}")
                            # 记录警告并继续
                            try:
                                # 1. 隐藏画框
                                highlight_client.hide_wnd()
                                time.sleep(0.1)

                                # 2. 准备异常信息
                                res = "{}".format(draw_result.error_message)
                            except Exception as cleanup_error:
                                logger.error("清理资源时出错: {}".format(cleanup_error))
                                res = "{}".format(draw_result.error_message)
                            finally:
                                # 3. 退出事件监听
                                self.service_context.event_core.close()

                            # 4. 设置响应信号，让 ws_server 能收到异常
                            del sign[PickerSign.START.value]
                            res_sign = "{}_RES".format(PickerSign.START.value)
                            sign[res_sign] = res

                            logger.info("拾取因异常结束")

                except Exception as e:
                    logger.error("pick error: {} {}".format(e, traceback.format_exc()))
            elif PickerSign.SMART_COMPONENT.value in sign:
                logger.info("智能组件上下拾取开始")
                res = self.service_context.picker_core.call_pluguin(
                    self.service_context, highlight_client, sign[PickerSign.SMART_COMPONENT.value]
                )
                del sign[PickerSign.SMART_COMPONENT.value]
                res_sign = "{}_RES".format(PickerSign.SMART_COMPONENT.value)
                sign[res_sign] = res
            else:
                # 3 休眠
                time.sleep(0.1)
