"""
运行日志管理 API 路由: 列表/下载/手动清理
日志文件由 executor 写入: logs/report/<project_id>/<exec_id>.txt (JSONL)
"""

import os
import time

from astronverse.scheduler.apis.response import ResCode, res_msg
from astronverse.scheduler.logger import logger
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()

# 运行日志根目录(executor 与 scheduler 同 cwd)
RUNLOG_DIR = os.path.join("logs", "report")


def _safe_log_dir() -> str:
    return os.path.abspath(RUNLOG_DIR)


def _is_under(dir_path: str, file_path: str) -> bool:
    """防止路径穿越: file_path 必须位于 dir_path 内。"""
    return os.path.commonpath([os.path.abspath(file_path), dir_path]) == dir_path


@router.get("/list")
def runlog_list(project_id: str = Query("", description="工程id, 空则全部")):
    """
    获取运行日志文件列表
    """
    try:
        base = _safe_log_dir()
        items = []
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
                    items.append(
                        {
                            "path": os.path.relpath(p, base),
                            "project_id": os.path.basename(root),
                            "exec_id": f[:-4],
                            "size": st.st_size,
                            "mtime": int(st.st_mtime),
                        }
                    )
        if project_id:
            items = [i for i in items if i["project_id"] == project_id]
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return res_msg(code=ResCode.SUCCESS, msg="success", data={"total": len(items), "list": items})
    except Exception as e:
        logger.exception(f"获取运行日志列表失败: {e}")
        return res_msg(code=ResCode.ERR, msg=str(e), data=None)


@router.get("/download")
def runlog_download(path: str = Query(..., description="日志相对路径")):
    """
    下载运行日志文件
    """
    base = _safe_log_dir()
    full = os.path.abspath(os.path.join(base, path))
    if not _is_under(base, full) or not os.path.isfile(full):
        return res_msg(code=ResCode.ERR, msg="文件不存在", data=None)
    return FileResponse(full, filename=os.path.basename(full), media_type="text/plain")


class ClearRequest(BaseModel):
    """手动清理请求"""

    project_id: str = ""  # 空=全部工程
    before_days: int = 0  # 清理N天前的, 0=全部


@router.post("/clear")
def runlog_clear(req: ClearRequest):
    """
    手动清理运行日志
    """
    try:
        base = _safe_log_dir()
        if not os.path.isdir(base):
            return res_msg(code=ResCode.SUCCESS, msg="success", data={"removed": 0})
        deadline = time.time() - req.before_days * 86400
        removed = 0
        for root, _, files in os.walk(base):
            if req.project_id and os.path.basename(root) != req.project_id:
                continue
            for f in files:
                if not f.endswith(".txt"):
                    continue
                p = os.path.join(root, f)
                try:
                    if req.before_days <= 0 or os.path.getmtime(p) < deadline:
                        os.remove(p)
                        removed += 1
                except OSError:
                    pass
        return res_msg(code=ResCode.SUCCESS, msg="success", data={"removed": removed})
    except Exception as e:
        logger.exception(f"清理运行日志失败: {e}")
        return res_msg(code=ResCode.ERR, msg=str(e), data=None)
