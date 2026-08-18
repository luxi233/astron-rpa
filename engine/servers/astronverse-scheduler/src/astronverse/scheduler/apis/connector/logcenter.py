"""
统一日志中心 API 路由: 管理设计器全部日志, 按类别分类配置保留策略

类别:
- run    流程运行日志: logs/report/<project_id>/<exec_id>.txt (JSONL, executor 写入)
- engine 引擎自身日志: logs/ 下 executor-*.log(执行器) scheduler-*.log(调度器)
        main.log(设计器 Electron 主进程) 及其轮转 zip

保留策略(与前端设置中心"运行日志"共用 .setting.json):
- logSetting.runRetentionDays    流程日志保留天数(默认30)
- logSetting.engineRetentionDays 引擎日志保留天数(默认7)
- 兼容旧字段 logSetting.retentionDays: 存在时作为两类初始值

注: loguru 的 retention 只匹配当前 sink 文件名的 glob, 而引擎日志按天命名
(executor-2026-08-18.log), 旧日期文件永远不匹配新模式, 因此本路由启动时
按 mtime 手动清理; baseline Logger.init 亦按同配置清理(executor/scheduler 各自进程)。
"""

import os
import time
from operator import itemgetter

from astronverse.scheduler.apis.response import ResCode, res_msg
from astronverse.scheduler.logger import logger
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter()

# 日志根目录(executor/scheduler/electron 与 cwd 一致)
LOG_BASE_DIR = "logs"
RUNLOG_DIR = os.path.join(LOG_BASE_DIR, "report")

# 引擎日志单次读取上限
MAX_TAIL_LINES = 5000
MAX_READ_BYTES = 4 * 1024 * 1024  # 4MB

# 默认保留天数
DEFAULT_RUN_RETENTION_DAYS = 30
DEFAULT_ENGINE_RETENTION_DAYS = 7


def load_retention_config() -> tuple[int, int]:
    """
    读取用户日志保留配置 <cwd>/.setting.json。
    返回 (runRetentionDays, engineRetentionDays), 兼容旧 retentionDays 字段。
    """
    run_days = DEFAULT_RUN_RETENTION_DAYS
    engine_days = DEFAULT_ENGINE_RETENTION_DAYS
    try:
        import json

        cfg_path = os.path.join(os.getcwd(), ".setting.json")
        if os.path.isfile(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            setting = cfg.get("logSetting") or {}
            legacy = setting.get("retentionDays")
            if isinstance(legacy, int) and legacy > 0:
                run_days = legacy
                engine_days = min(legacy, DEFAULT_ENGINE_RETENTION_DAYS)
            rd = setting.get("runRetentionDays")
            if isinstance(rd, int) and rd > 0:
                run_days = rd
            ed = setting.get("engineRetentionDays")
            if isinstance(ed, int) and ed > 0:
                engine_days = ed
    except (OSError, ValueError):
        pass
    return run_days, engine_days


def _is_under(dir_path: str, file_path: str) -> bool:
    """防止路径穿越: file_path 必须位于 dir_path 内。"""
    return os.path.commonpath([os.path.abspath(file_path), dir_path]) == dir_path


# ---------------------- 列表 ----------------------


@router.get("/list")
def log_list(
    category: str = Query("run", description="日志类别: run=流程日志, engine=引擎日志"),
    project_id: str = Query("", description="工程id, 仅run类别, 空则全部"),
):
    """
    获取日志文件列表(按类别)
    """
    try:
        items = []
        if category == "engine":
            base = os.path.abspath(LOG_BASE_DIR)
            if os.path.isdir(base):
                for f in os.listdir(base):
                    if not f.endswith(".log") and not f.endswith(".zip"):
                        continue
                    p = os.path.join(base, f)
                    if not os.path.isfile(p):
                        continue
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    items.append({"name": f, "size": st.st_size, "mtime": int(st.st_mtime)})
            items.sort(key=itemgetter("mtime"), reverse=True)
            return res_msg(code=ResCode.SUCCESS, msg="success", data={"dir": base, "total": len(items), "list": items})

        # 默认: 流程日志(递归 report 目录)
        base = os.path.abspath(RUNLOG_DIR)
        if os.path.isdir(base):
            for root, _, files in os.walk(base):
                for f in files:
                    if not f.endswith(".txt"):
                        continue
                    p = os.path.join(root, f)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    pid = os.path.basename(root)
                    if project_id and pid != project_id:
                        continue
                    items.append(
                        {
                            "path": os.path.relpath(p, base),
                            "project_id": pid,
                            "exec_id": f[:-4],
                            "size": st.st_size,
                            "mtime": int(st.st_mtime),
                        }
                    )
        items.sort(key=itemgetter("mtime"), reverse=True)
        return res_msg(code=ResCode.SUCCESS, msg="success", data={"total": len(items), "list": items})
    except Exception as e:
        logger.exception(f"获取日志列表失败: {e}")
        return res_msg(code=ResCode.ERR, msg=str(e), data=None)


# ---------------------- 下载 ----------------------


@router.get("/download")
def log_download(
    category: str = Query("run", description="日志类别: run=流程日志, engine=引擎日志"),
    path: str = Query(..., description="日志文件路径(run=相对report目录, engine=裸文件名)"),
):
    """
    下载日志文件
    """
    base = os.path.abspath(RUNLOG_DIR if category == "run" else LOG_BASE_DIR)
    full = os.path.abspath(os.path.join(base, path))
    if os.path.basename(path) != path and category == "engine":
        return res_msg(code=ResCode.ERR, msg="非法文件名", data=None)
    if not _is_under(base, full) or not os.path.isfile(full):
        return res_msg(code=ResCode.ERR, msg="文件不存在", data=None)
    return FileResponse(full, filename=os.path.basename(full), media_type="text/plain")


# ---------------------- 引擎日志尾读 ----------------------


class LogReadRequest(BaseModel):
    """引擎日志尾部读取请求"""

    filename: str = Field(..., description="日志文件名(仅 basename, 不允许路径)")
    tail_lines: int = Field(500, ge=1, le=MAX_TAIL_LINES, description="读取尾部行数")


@router.post("/read")
def log_read(req: LogReadRequest):
    """
    尾部读取引擎日志文件内容
    """
    try:
        base = os.path.abspath(LOG_BASE_DIR)
        # 防路径穿越: 只允许 logs 目录下的裸文件名
        if os.path.basename(req.filename) != req.filename:
            return res_msg(code=ResCode.ERR, msg="非法文件名", data=None)
        full = os.path.abspath(os.path.join(base, req.filename))
        if not _is_under(base, full) or not os.path.isfile(full):
            return res_msg(code=ResCode.ERR, msg="文件不存在", data=None)

        size = os.path.getsize(full)
        with open(full, "rb") as f:
            # 只读尾部 MAX_READ_BYTES, 大文件避免全量加载
            read_bytes = min(size, MAX_READ_BYTES)
            f.seek(max(0, size - read_bytes))
            raw = f.read(read_bytes)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        # 若发生了截断, 丢弃不完整的首行
        if read_bytes < size and lines:
            lines = lines[1:]
        lines = lines[-req.tail_lines :]

        return res_msg(
            code=ResCode.SUCCESS,
            msg="success",
            data={
                "filename": req.filename,
                "size": size,
                "truncated": size > MAX_READ_BYTES,
                "lines": lines,
            },
        )
    except Exception as e:
        logger.exception(f"读取引擎日志失败: {e}")
        return res_msg(code=ResCode.ERR, msg=str(e), data=None)


# ---------------------- 清理 ----------------------


class LogClearRequest(BaseModel):
    """手动清理请求"""

    category: str = Field("all", description="清理类别: run=流程日志, engine=引擎日志, all=全部")
    before_days: int = Field(0, ge=0, description="清理N天前的, 0=全部(engine类别仍保护正在写入的文件)")
    project_id: str = Field("", description="仅run类别: 按工程清理, 空=全部工程")


def _clear_run(before_days: int, project_id: str = "") -> int:
    base = os.path.abspath(RUNLOG_DIR)
    if not os.path.isdir(base):
        return 0
    deadline = time.time() - before_days * 86400
    removed = 0
    for root, _, files in os.walk(base):
        pid = os.path.basename(root)
        if project_id and pid != project_id:
            continue
        for f in files:
            if not f.endswith(".txt"):
                continue
            p = os.path.join(root, f)
            try:
                if before_days <= 0 or os.path.getmtime(p) < deadline:
                    os.remove(p)
                    removed += 1
            except OSError:
                pass
    return removed


def _clear_engine(before_days: int) -> int:
    base = os.path.abspath(LOG_BASE_DIR)
    if not os.path.isdir(base):
        return 0
    deadline = time.time() - before_days * 86400
    today = time.strftime("%Y-%m-%d")
    removed = 0
    for f in os.listdir(base):
        p = os.path.join(base, f)
        if not os.path.isfile(p) or not (f.endswith(".log") or f.endswith(".zip")):
            continue
        # 保护正在写入的文件: 当天日期命名的引擎日志 + main.log(electron-log 单文件滚动)
        if f == "main.log" or today in f:
            continue
        try:
            if before_days <= 0 or os.path.getmtime(p) < deadline:
                os.remove(p)
                removed += 1
        except OSError:
            pass
    return removed


@router.post("/clear")
def log_clear(req: LogClearRequest):
    """
    手动清理日志(按类别)
    """
    try:
        removed = 0
        if req.category in ("run", "all"):
            removed += _clear_run(req.before_days, req.project_id)
        if req.category in ("engine", "all"):
            removed += _clear_engine(req.before_days)
        return res_msg(code=ResCode.SUCCESS, msg="success", data={"removed": removed})
    except Exception as e:
        logger.exception(f"清理日志失败: {e}")
        return res_msg(code=ResCode.ERR, msg=str(e), data=None)


# ---------------------- 启动自动清理 ----------------------


@router.on_event("startup")
async def startup_event():
    async def startup():
        # scheduler 启动时按用户配置自动清理过期日志
        # (引擎日志由 baseline Logger.init 在各进程启动时同样清理, 此处兜底)
        run_days, engine_days = load_retention_config()
        removed = _clear_run(run_days)
        removed += _clear_engine(engine_days)
        if removed:
            logger.info(f"日志中心启动自动清理 {removed} 个过期文件(run={run_days}天, engine={engine_days}天)")

    import asyncio

    task = asyncio.create_task(startup())
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
