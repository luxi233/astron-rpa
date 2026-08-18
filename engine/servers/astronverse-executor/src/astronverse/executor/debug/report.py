import copy
import json
import os
import queue
import time
from dataclasses import asdict
from enum import Enum
from queue import Queue

from astronverse.actionlib import (
    ReportCode,
    ReportCodeStatus,
    ReportFlow,
    ReportScript,
    ReportTip,
    ReportType,
    ReportUser,
)
from astronverse.actionlib.report import IReport

# 日志缓冲刷盘间隔: 首条立即刷(流程启动消息即时可见), 之后按此间隔批量刷, close/退出兜底
_FLUSH_INTERVAL_SECONDS = 2.0


class Report(IReport):
    """运行日志处理程序"""

    def __init__(self, svc):
        self.svc = svc
        self.queue = Queue(maxsize=1000)
        self._last_flush_time = 0.0
        local_file_path = os.path.join(self.svc.conf.log_path, "report", self.svc.conf.project_id)
        if not os.path.exists(local_file_path):
            os.makedirs(local_file_path)
        self.log_local_file = open(
            os.path.join(str(local_file_path), "{}.txt".format(self.svc.conf.exec_id)), "w", encoding="utf-8"
        )
        # 按保留时限清理过期的运行日志
        self.clean_expired_logs(self.svc.conf.log_path, self.svc.conf.log_retention_days)
        self._init_process()

    @staticmethod
    def clean_expired_logs(log_path: str, retention_days: int):
        """删除 report/ 下超过保留时限的运行日志文件（按文件修改时间）。"""
        if not log_path or not retention_days or retention_days <= 0:
            return
        report_dir = os.path.join(log_path, "report")
        if not os.path.isdir(report_dir):
            return
        deadline = time.time() - retention_days * 86400
        for root, _, files in os.walk(report_dir):
            for f in files:
                if not f.endswith(".txt"):
                    continue
                p = os.path.join(root, f)
                try:
                    if os.path.getmtime(p) < deadline:
                        os.remove(p)
                except OSError:
                    pass

    def _init_process(self):
        self.process = {}
        for i, v in self.svc.ast_globals.process_info.items():
            process_meta = {}
            if v.process_meta:
                for m in v.process_meta:
                    process_meta[m[0]] = m
            new_v = copy.copy(v)
            new_v.process_meta = process_meta
            self.process[v.process_id] = new_v

        self.last_process_id = ""
        self.last_line = 0

    def close(self):
        self.flush()
        self.log_local_file.close()

    def flush(self):
        """将缓冲中的日志刷入磁盘(读文件前/close/进程退出时调用)"""
        if self.log_local_file and not self.log_local_file.closed:
            self.log_local_file.flush()
        self._last_flush_time = time.time()

    @staticmethod
    def __json__(obj):
        if isinstance(obj, Enum):
            return obj.value
        else:
            return obj.__dict__

    def __send__(self, filtered_dict):
        if self.queue and self.svc.conf.open_log_ws:
            ms = json.dumps(filtered_dict, ensure_ascii=False, default=self.__json__)
            try:
                # ws消费过慢时最多等5s, 队列满则丢弃该条, 不阻塞流程执行
                self.queue.put(ms, block=True, timeout=5)
            except queue.Full:
                pass

        if (
            self.log_local_file
            and (not self.log_local_file.closed)
            and filtered_dict["log_type"] != ReportType.Tip
            and filtered_dict.get("tag", None) != "tip"
        ):
            # Tip数据不写入到日志里面, tag等于Tag也不写入到日志
            message = json.dumps(
                {"event_time": int(time.time()), "data": filtered_dict}, ensure_ascii=False, default=self.__json__
            )
            self.log_local_file.write(f"{message}\n")
            # 缓冲写: 首条立即落盘(流程启动消息即时可见), 之后每2s刷一次, close/退出兜底
            if time.time() - self._last_flush_time >= _FLUSH_INTERVAL_SECONDS:
                self.log_local_file.flush()
                self._last_flush_time = time.time()

    def __pre__(self, message):
        if (
            isinstance(message, ReportFlow)
            or isinstance(message, ReportCode)
            or isinstance(message, ReportUser)
            or isinstance(message, ReportTip)
        ):
            pass
        else:
            process_id, line = self.svc.debug.find_log_position()
            if process_id in self.process:
                message = ReportScript(msg_str=str(message), process_id=process_id, line=line)
            else:
                message = ReportScript(msg_str=str(message))

        if isinstance(message, ReportCode) or isinstance(message, ReportUser) or isinstance(message, ReportScript):
            if message.process_id in self.process:
                # 本工程
                process_id = message.process_id
                line = message.line
                self.last_line = line
                self.last_process_id = process_id
            else:
                # 非本工程, 组件
                process_id = self.last_process_id
                line = self.last_line
                message.process_id = self.last_process_id
                message.line = self.last_line

            # 填充普通数据数据
            process = self.process[process_id]
            process_name = process.process_name
            if not message.process:
                message.process = process_name
                message.msg_str = message.msg_str.replace("{process}", process_name)
            if line in process.process_meta:
                meta = process.process_meta[line]
                atomic = meta[2]
                key = meta[3]
                line_id = meta[1]
                if hasattr(message, "atomic") and not message.atomic:
                    message.atomic = atomic
                    message.msg_str = message.msg_str.replace("{atomic}", atomic)
                if hasattr(message, "key") and not message.key:
                    message.key = key
                    message.msg_str = message.msg_str.replace("{key}", key)
                if hasattr(message, "line_id") and not message.line_id:
                    message.line_id = line_id
                    message.msg_str = message.msg_str.replace("{line_id}", line_id)
        return message

    def info(self, message):
        message = self.__pre__(message)

        filtered_dict = {k: v for k, v in asdict(message).items() if v is not None}

        if isinstance(message, ReportCode):
            if message.status == ReportCodeStatus.START:
                filtered_dict["tag"] = "tip"  # 特殊处理，只发送给右下角tip
        filtered_dict["log_level"] = "info"
        return self.__send__(filtered_dict)

    def warning(self, message):
        message = self.__pre__(message)

        filtered_dict = {k: v for k, v in asdict(message).items() if v is not None}
        filtered_dict["log_level"] = "warning"
        return self.__send__(filtered_dict)

    def error(self, message):
        message = self.__pre__(message)

        filtered_dict = {k: v for k, v in asdict(message).items() if v is not None}
        filtered_dict["log_level"] = "error"
        return self.__send__(filtered_dict)
