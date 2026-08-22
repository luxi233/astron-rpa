import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from astronverse.scheduler.logger import logger
from astronverse.scheduler.utils.utils import kill_proc_tree


def disable_cmd_quick_edit():
    # window特有的
    if sys.platform == "win32":
        import ctypes

        # 定义常量
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080

        # 获取标准输入的句柄
        kernel32 = ctypes.windll.kernel32
        hStdin = kernel32.GetStdHandle(-10)

        # 获取当前输入模式
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(hStdin, ctypes.byref(mode))

        # 禁用快速编辑模式
        mode.value &= ~ENABLE_QUICK_EDIT_MODE
        mode.value |= ENABLE_EXTENDED_FLAGS

        # 设置新的输入模式
        kernel32.SetConsoleMode(hStdin, mode)


def default_output_callback(msg):
    logger.info("[RES]{}".format(msg))


def async_default_output_callback(msg, error):
    if error:
        logger.info("[ERR]{}".format(error))
    else:
        logger.info("[RES]{}".format(msg))


def get_log_dir() -> str:
    """日志目录(与 scheduler 自身日志同目录): <cwd>/logs"""
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# 崩溃留痕: 进程死亡时回读子进程 stderr 文件尾部的字节数上限(超长的仅取尾部)
CRASH_TAIL_BYTES = 8192


class SubPopen:
    def __init__(self, name: str = None, cmd: list = None, params: dict = None):
        if not params:
            params = {}
        if not cmd:
            cmd = []
        self.name = name
        self.cmd = cmd
        self.params = params
        self.proc = None
        self.start_time = 0
        self.__log__ = None
        self.__stderr_file__ = None

    def logger_handler(self, output_callback=default_output_callback, timeout=None) -> (str, str):
        if self.__log__:

            def read_stdout(pipe, callback):
                """读取标准输出的线程函数"""
                try:
                    for text in iter(pipe.readline, ""):
                        if callback:
                            callback(text.strip())
                except Exception:
                    pass

            stdout_thread = threading.Thread(
                target=read_stdout,
                args=(self.proc.stdout, output_callback),
                daemon=True,
            )
            stdout_thread.start()

            self.proc.wait(timeout=timeout)
            stdout_thread.join()

            stderr_data = self.proc.stderr.read()
            return "", stderr_data
        else:
            return self.proc.communicate(timeout=timeout)

    def async_logger_handler(self, output_callback=async_default_output_callback):
        if not self.__log__:
            # 不支持没有日志的情况
            return

        def read_stdout(proc, callback):
            """读取标准输出的线程函数"""
            try:
                for text in iter(proc.stdout.readline, ""):
                    if callback:
                        callback(text.strip())
            except Exception as e:
                pass
            finally:
                proc.wait()
                stderr = proc.stderr.read()
                if proc.returncode != 0 and callback:
                    callback("", stderr)
                else:
                    pass

        stdout_thread = threading.Thread(target=read_stdout, args=(self.proc, output_callback), daemon=True)
        stdout_thread.start()
        return

    def run(
        self, shell: bool = None, log: bool = False, encoding="utf-8", env=None, stderr_log: str = None
    ) -> "SubPopen":
        disable_cmd_quick_edit()
        # 上一轮进程死亡时先收殓退出码与 stderr 尾部(崩溃留痕, 避免静默死亡无诊断信息)
        self._harvest_previous()

        # shell 默认值
        if shell is None:
            if sys.platform == "win32":
                shell = True
            else:
                shell = False

        # 参数
        param_list = [f"--{key}={shlex.quote(str(value))}" for key, value in self.params.items()]
        cmd = self.cmd + param_list
        logger.info(
            "cmd: {} env".format(
                cmd,
            )
        )

        # 启动是否包含log
        self.start_time = time.time()

        # 注意部分命令执行不能加env，对于拾取组件，加上env导致拾取进程启动异常
        if env is None:
            current_env = os.environ.copy()
            current_env["no_proxy"] = "True"
            env = current_env if "pip" in cmd else None

        self.__log__ = log

        # 崩溃留痕: 不开全量日志时, 可将 stderr 重定向到文件捕获崩溃信息(如 Python traceback)
        self.__stderr_file__ = None
        if not log and stderr_log:
            try:
                self.__stderr_file__ = open(stderr_log, "w", encoding=encoding, errors="replace")  # noqa: SIM115
            except Exception as e:
                logger.warning("stderr 重定向文件打开失败 {}: {}".format(stderr_log, e))

        self.proc = subprocess.Popen(
            cmd,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if log else subprocess.DEVNULL,
            stderr=subprocess.PIPE if log else (self.__stderr_file__ or subprocess.DEVNULL),
            text=True,
            env=env,
            encoding=encoding,
            errors="replace",
        )
        return self

    def _harvest_previous(self):
        """重启前收殓上一轮子进程: 记录退出码, 并回读 stderr 重定向文件尾部写入调度器日志"""
        if self.proc is None:
            return
        returncode = self.proc.poll()
        if returncode is None:
            return
        tail = ""
        if self.__stderr_file__:
            path = getattr(self.__stderr_file__, "name", "")
            try:
                self.__stderr_file__.close()
            except Exception:
                pass
            self.__stderr_file__ = None
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                tail = content[-CRASH_TAIL_BYTES:] if content else ""
            except Exception:
                pass
        logger.error(
            "子进程 {} 已退出, returncode={}{}".format(
                self.name, returncode, ", stderr尾部:\n{}".format(tail) if tail.strip() else ""
            )
        )

    def set_param(self, key, val):
        """
        设置参数
        """
        self.params[key] = val

    def get_param(self, key):
        """
        获取参数
        """
        return self.params[key]

    def is_alive(self):
        """
        判断子进程是否存活
        """
        return self.proc is not None and self.proc.poll() is None

    def kill(self):
        if self.proc:
            try:
                # 如果已经关闭可能报错
                kill_proc_tree(psutil.Process(self.proc.pid), including_parent=True)
                self.proc.wait()
            except Exception as e:
                pass
