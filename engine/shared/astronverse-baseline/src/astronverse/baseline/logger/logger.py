import json
import os
import time

from loguru import logger as log

# 引擎日志默认保留天数(进程启动时清理过期文件)
DEFAULT_RETENTION_DAYS = 7


def load_retention_days() -> int:
    """
    从用户设置(<cwd>/.setting.json)读取引擎日志保留天数。
    字段优先级: logSetting.engineRetentionDays > logSetting.retentionDays(旧) > 默认7天。
    """
    try:
        cfg_path = os.path.join(os.getcwd(), ".setting.json")
        if os.path.isfile(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            setting = cfg.get("logSetting") or {}
            days = setting.get("engineRetentionDays")
            if isinstance(days, int) and days > 0:
                return days
            legacy = setting.get("retentionDays")
            if isinstance(legacy, int) and legacy > 0:
                return min(legacy, DEFAULT_RETENTION_DAYS)
    except (OSError, ValueError):
        pass
    return DEFAULT_RETENTION_DAYS


def cleanup_old_logs(log_dir: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """
    清理过期的引擎日志文件。
    注: loguru 的 retention 只匹配当前 sink 文件名的 glob, 而日志按天命名
    (executor-2026-08-18.log), 旧日期文件永远不匹配新模式, 需在启动时按 mtime 手动清理。
    """
    deadline = time.time() - retention_days * 86400
    removed = 0
    if not os.path.isdir(log_dir):
        return 0
    for f in os.listdir(log_dir):
        p = os.path.join(log_dir, f)
        if not os.path.isfile(p) or not (f.endswith(".log") or f.endswith(".zip")):
            continue
        try:
            if os.path.getmtime(p) < deadline:
                os.remove(p)
                removed += 1
        except OSError:
            # Windows 下文件被占用时跳过
            pass
    return removed


class Logger:
    """Logger"""

    def __init__(self):
        self.logger = log

    def init(self, name: str = ""):
        if not name:
            return
        self.logger.remove()
        log_path = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(log_path):
            os.mkdir(log_path)

        # 保留天数跟随用户设置(与流程日志"保留时限"共用), 默认7天
        retention_days = load_retention_days()

        # 启动时清理过期日志(loguru retention 对按天命名的旧文件无效)
        cleanup_old_logs(log_path, retention_days)

        # Time-rotated log file
        log_path = os.path.abspath(os.path.join(log_path, "{}-{}.log".format(name, time.strftime("%Y-%m-%d"))))
        self.logger.add(
            log_path,
            rotation="50MB",
            retention="{} days".format(retention_days),
            encoding="utf-8",
            enqueue=True,
            compression="zip",
        )

    def get_log(self):
        return self.logger


base_logger = Logger()
base_logger.init()
logger = base_logger.get_log()
