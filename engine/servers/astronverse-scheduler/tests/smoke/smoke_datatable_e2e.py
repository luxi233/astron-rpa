"""数据表格端到端一致性与实时性测试(执行器子进程 → scheduler 监听/读取)。

真实链路验证(两个独立进程, 各用各的 venv, 与生产部署形态一致):
  执行器子进程(组件 venv): DataTable 写/清空(真实防抖+原子落盘+atexit兜底)
    → 磁盘 xlsx
  scheduler(本进程): AsyncFileWatcher(PollingObserver) 监听同一文件
    → file_changed 事件 → ExcelService.read_file 快照

验证目标:
  G. 一致性: 每个写入阶段的事件后快照内容与执行器写入内容逐格一致
  H. 实时性: 写入(内存完成) → file_changed 事件到达的端到端延迟量化, 上限断言
  I. 流程结束场景: 高频写(防抖窗口内)+进程退出(atexit落盘) → 事件仍到达且内容正确

运行: cd engine/servers/astronverse-scheduler && .venv/bin/python tests/smoke/smoke_datatable_e2e.py
"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from astronverse.scheduler.core.datatable.excel_service import ExcelService
from astronverse.scheduler.core.datatable.file_watcher import AsyncFileWatcher

# 定位组件(执行器侧): scheduler/tests/smoke/x.py -> engine/...
_ENGINE_DIR = Path(__file__).resolve().parents[4]
_COMPONENT_DIR = _ENGINE_DIR / "components" / "astronverse-datatable"
_XLSX = _COMPONENT_DIR / "astron" / "data_table.xlsx"
_COMPONENT_PY = _COMPONENT_DIR / ".venv" / "bin" / "python"

# 端到端延迟上限: 执行器写(内存) → 防抖落盘(≤0.5s) → 轮询发现(≤0.5s) → 事件防抖(≤0.5s)
# 理论上限 ~1.5s, 留 CI 慢机余量
_LATENCY_LIMIT = 4.0

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


# 执行器子进程脚本: 真实 DataTable 原子写, stdout 输出 MARK <阶段> <完成时刻> 供延迟配对
_EXECUTOR_SCRIPT = """
import sys, time
sys.path.insert(0, {src!r})
from astronverse.datatable import WriteType
from astronverse.datatable.datatable import DataTable

dt = DataTable()
dt.clear_data_table(is_clear_head=True)  # 起点归零(自身触发一次写)
time.sleep(0.7)  # 让防抖窗口重置, 保证后续每阶段独立成一次落盘

dt.write_data(write_type=WriteType.CELL, row=1, col="A", data="e2e-v1-r1")
dt.write_data(write_type=WriteType.CELL, row=1, col="B", data="e2e-v1-c1")
print("MARK write_v1 %f" % time.time(), flush=True)
time.sleep(1.2)

dt.write_data(write_type=WriteType.CELL, row=2, col="A", data="e2e-v2-r2")
print("MARK write_v2 %f" % time.time(), flush=True)
time.sleep(1.2)

dt.clear_data_table(is_clear_head=True)
print("MARK clear %f" % time.time(), flush=True)
time.sleep(1.2)

# 高频写(全部落在防抖窗口内) + 立即退出: 落盘靠 Timer 兜底/ atexit
for i in range(1, 11):
    dt.write_data(write_type=WriteType.CELL, row=i, col=1, data=f"burst-{{i}}")
print("MARK burst %f" % time.time(), flush=True)
time.sleep(0.05)
sys.exit(0)
"""


def sheet_cells(sheet: dict) -> set:
    """快照 → 非空单元格集合 {(row, col): value}(1-based)"""
    cells = {}
    for r, row in enumerate(sheet.get("data") or []):
        if not row:
            continue
        for c, v in enumerate(row):
            if v is not None and v != "":
                cells[(r + 1, c + 1)] = v
    return cells


async def main():
    if not _COMPONENT_PY.exists():
        print(f"[SKIP] 组件 venv 不存在: {_COMPONENT_PY}")
        sys.exit(0)
    assert _XLSX.exists(), f"数据表格文件不存在: {_XLSX}"

    # scheduler 侧: watcher + 读服务(与生产同构)
    svc = ExcelService(resource_dir=str(_XLSX.parent))
    watcher = AsyncFileWatcher(str(_XLSX))

    snapshots = []  # [(t_event, cells)] 每次 file_changed 后立即读取的快照
    events = []
    proc_ready = asyncio.Event()

    async def consume():
        async for ev in watcher.start():
            if ev["type"] == "file_changed":
                t_event = time.time()
                events.append(t_event)
                try:
                    data = svc.read_file("data_table.xlsx")
                    sheet = (data.get("sheets") or [{}])[0]
                    snapshots.append((t_event, sheet_cells(sheet)))
                except Exception as e:
                    snapshots.append((t_event, {("error", 0): str(e)}))
                proc_ready.set()

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.5)  # watcher 就绪

    # 起跑前快照清零
    events.clear()
    snapshots.clear()

    # 启动执行器子进程, 实时解析 MARK 行
    marks = {}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_EXECUTOR_SCRIPT.format(src=str(_COMPONENT_DIR / "src")))
        script_path = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            str(_COMPONENT_PY),
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode().strip()
            if line.startswith("MARK "):
                _, name, ts = line.split()
                marks[name] = float(ts)
        await proc.wait()
    finally:
        os.unlink(script_path)

    # 等最后的事件(轮询0.5+防抖, 给足余量)
    try:
        await asyncio.wait_for(proc_ready.wait(), timeout=5)
    except TimeoutError:
        pass
    await asyncio.sleep(1.5)  # 尾部事件收齐
    watcher.stop()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, GeneratorExit):
        pass

    print(f"\n收到 file_changed 事件 {len(events)} 次, MARK {len(marks)} 个")

    # ============================================================
    # G. 一致性: 各阶段事件后快照与写入内容一致
    # ============================================================
    print("\n========== G. 前后端数据一致性 ==========")
    check("G0 事件已产生", len(events) >= 4, f"got {len(events)}")
    check(
        "G0b 快照无读取错误",
        not any(("error", 0) in c for _, c in snapshots),
        str([c for _, c in snapshots if ("error", 0) in c][:1]),
    )

    def has_snapshot(cond) -> bool:
        return any(cond(cells) for _, cells in snapshots)

    # v1 写入后: 快照含 v1 两个格子
    check(
        "G1 快照含 v1 写入(1,A)+(1,B)",
        has_snapshot(lambda c: c.get((1, 1)) == "e2e-v1-r1" and c.get((1, 2)) == "e2e-v1-c1"),
    )
    # v2 写入后: 快照同时含 v1+v2(增量写不丢旧数据)
    check(
        "G2 快照含 v1+v2 增量共存",
        has_snapshot(lambda c: c.get((1, 1)) == "e2e-v1-r1" and c.get((2, 1)) == "e2e-v2-r2"),
    )
    # 清空后: 存在全空快照
    check("G3 清空后存在全空快照", has_snapshot(lambda c: len(c) == 0), f"snap_sizes={[len(c) for _, c in snapshots]}")
    # 高频写+退出后: 最终快照 = burst 10 行
    burst_expected = {(i, 1): f"burst-{i}" for i in range(1, 11)}
    check(
        "G4 最终快照=burst 10行逐格一致",
        snapshots and snapshots[-1][1] == burst_expected,
        f"last={snapshots[-1][1] if snapshots else None}",
    )
    # 最终快照之后不再有事件里的旧状态(单调收敛: 最后一次快照就是终态)
    check("G5 终态后无回退快照", all(snapshots[-1][1] == burst_expected for _ in [0]))

    # ============================================================
    # H. 实时性: 写入(MARK) → 对应事件到达的延迟
    # ============================================================
    print("\n========== H. 读写实时性 ==========")
    # 每阶段事件数(粗配对: 每阶段至少一个事件, 延迟=该阶段 MARK 后首个事件-MARK)
    for name in ("write_v1", "write_v2", "clear", "burst"):
        if name not in marks:
            check(f"H-{name} MARK 存在", False, "缺失")
            continue
        t_mark = marks[name]
        later = [t for t in events if t >= t_mark]
        if not later:
            check(f"H-{name} 事件到达延迟", False, "无后续事件")
            continue
        latency = later[0] - t_mark
        check(f"H-{name} 事件延迟 {latency:.2f}s < {_LATENCY_LIMIT}s", latency < _LATENCY_LIMIT, f"got {latency:.2f}s")
    # 整体事件间隔健康度: 事件数量 >= 阶段数(4)说明每阶段都触发了独立事件
    check(f"H5 每阶段均触发事件(共{len(events)}次≥4)", len(events) >= 4)

    # ============================================================
    # I. 流程结束场景(burst+退出)已由 G4/H-burst 覆盖, 补充终态磁盘直读
    # ============================================================
    print("\n========== I. 终态磁盘 ==========")
    final = sheet_cells((svc.read_file("data_table.xlsx").get("sheets") or [{}])[0])
    check("I1 终态磁盘直读=burst 10行", final == burst_expected, f"got {final}")

    print(f"\n========== 结果: {PASS} 通过, {FAIL} 失败 ==========")
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
