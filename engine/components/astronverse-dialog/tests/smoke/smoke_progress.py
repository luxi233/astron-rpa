# -*- coding: utf-8 -*-
"""M11 P5-7 进度条×3 冒烟测试：mock ws 通道验证消息协议与迭代器包装"""

import sys

from astronverse.actionlib.atomic import atomicMg
from astronverse.dialog.dialog import Dialog, ProgressBar

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")


class FakeWs:
    """模拟 executor ws：记录 send_notification 调用"""

    def __init__(self, raise_on_send=False):
        self.sent = []
        self.raise_on_send = raise_on_send

    def send_notification(self, msg):
        if self.raise_on_send:
            raise ConnectionError("ws 断连模拟")
        self.sent.append(msg)

    def options(self):
        return [m["data"]["option"] for m in self.sent]

    def names(self):
        return [m["data"]["name"] for m in self.sent]


print("== 1. init_progress_bar：open 消息协议 ==")
ws = FakeWs()
atomicMg.cfg()["WS"] = ws
pb = Dialog.init_progress_bar([10, 20, 30], title="批量处理", task_name="下载文件")
check("返回 ProgressBar 对象", isinstance(pb, ProgressBar))
check("消息 name=progress", ws.names() == ["progress"], str(ws.names()))
opt = ws.options()[0]
check("operate=open", opt["operate"] == "open")
check("key=Dialog.init_progress_bar", opt["key"] == "Dialog.init_progress_bar")
check("percent=0", opt["percent"] == 0)
check("total=3", opt["total"] == 3)
check("current=0", opt["current"] == 0)
check("title 透传", opt["title"] == "批量处理")
check("task_name=初始描述", opt["task_name"] == "下载文件")
check("progress_id 非空", bool(opt["progress_id"]))
pid = opt["progress_id"]

print("== 2. 循环消费：自动推进 + close ==")
items = list(pb)
check("迭代结果正确", items == [10, 20, 30], str(items))
opts = ws.options()
check("共5条消息 open+3update+close", len(opts) == 5, str(len(opts)))
check("update1 percent=33 current=1", opts[1]["percent"] == 33 and opts[1]["current"] == 1)
check("update2 percent=67 current=2", opts[2]["percent"] == 67 and opts[2]["current"] == 2)
check("update3 percent=100 current=3", opts[3]["percent"] == 100 and opts[3]["current"] == 3)
check("close operate=close percent=100", opts[4]["operate"] == "close" and opts[4]["percent"] == 100)
check("progress_id 全程一致", all(o["progress_id"] == pid for o in opts))

print("== 3. 生成器（无 len）：未知总数模式 ==")
ws2 = FakeWs()
atomicMg.cfg()["WS"] = ws2


def gen():
    yield "a"
    yield "b"


pb2 = Dialog.init_progress_bar(gen(), title="", task_name="")
opts2 = ws2.options()
check("total=0", opts2[0]["total"] == 0)
vals = [x for x in pb2]
check("迭代正常", vals == ["a", "b"], str(vals))
opts2 = ws2.options()
check("未知总数 percent=None", opts2[1]["percent"] is None, str(opts2[1]))
check("title 空回退默认", opts2[0]["title"] == "任务进度")

print("== 4. update_progress 手动更新 ==")
ws3 = FakeWs()
atomicMg.cfg()["WS"] = ws3
pb3 = Dialog.init_progress_bar([1, 2, 3, 4])
ws3.sent.clear()  # 清掉 open
Dialog.update_progress(progress_bar=pb3, percent=50)
opt = ws3.options()[0]
check("手动 update percent=50", opt["operate"] == "update" and opt["percent"] == 50)
Dialog.update_progress(progress_bar=pb3, percent=150)
check("越界 150→100", ws3.options()[1]["percent"] == 100)
Dialog.update_progress(progress_bar=pb3, percent=-10)
check("越界 -10→0", ws3.options()[2]["percent"] == 0)
Dialog.update_progress(progress_bar=pb3, percent="abc")
check("非数字→0", ws3.options()[3]["percent"] == 0)

print("== 5. set_progress_description ==")
ws4 = FakeWs()
atomicMg.cfg()["WS"] = ws4
pb4 = Dialog.init_progress_bar([1, 2], task_name="旧描述")
ws4.sent.clear()
Dialog.set_progress_description(progress_bar=pb4, description="正在处理第3批")
opts4 = ws4.options()
check("描述更新推送", opts4[0]["task_name"] == "正在处理第3批", str(opts4[0]))
check("未迭代 percent=0", opts4[0]["percent"] == 0, str(opts4[0]))
next(iter(pb4))
opts4 = ws4.options()
check("迭代后描述保持", opts4[1]["task_name"] == "正在处理第3批")
check("迭代后 percent=50", opts4[1]["percent"] == 50)

print("== 6. 错误分支 ==")
try:
    Dialog.update_progress(progress_bar=None, percent=50)
    check("update 无效对象报错", False)
except ValueError as e:
    check("update 无效对象报错", "进度条对象无效" in str(e))
try:
    Dialog.set_progress_description(progress_bar="not_a_bar", description="x")
    check("set_description 无效对象报错", False)
except ValueError as e:
    check("set_description 无效对象报错", "进度条对象无效" in str(e))

print("== 7. ws 断连不阻断流程 ==")
ws5 = FakeWs(raise_on_send=True)
atomicMg.cfg()["WS"] = ws5
pb5 = Dialog.init_progress_bar([1, 2, 3])
vals = [x for x in pb5]
check("ws 异常时迭代照常完成", vals == [1, 2, 3], str(vals))

print("== 8. 空列表与无 ws 环境 ==")
ws6 = FakeWs()
atomicMg.cfg()["WS"] = ws6
pb6 = Dialog.init_progress_bar([])
check("空列表 open 正常", ws6.options()[0]["operate"] == "open" and ws6.options()[0]["total"] == 0)
check("空列表可迭代", list(pb6) == [])
atomicMg.cfg()["WS"] = None
pb7 = Dialog.init_progress_bar([1])
check("无 ws 不崩", next(iter(pb7)) == 1)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
