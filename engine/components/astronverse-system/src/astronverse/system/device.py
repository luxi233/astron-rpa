import os
import platform
import socket
import sys

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.system import *
from astronverse.system.error import *


def _require_win32():
    if sys.platform != "win32":
        raise BaseException(DEVICE_NOT_SUPPORTED_FORMAT, "当前系统非 Windows")


class Device:
    @staticmethod
    @atomicMg.atomic(
        "Device",
        inputList=[],
        outputList=[
            atomicMg.param("ip_address", types="Str"),
            atomicMg.param("host_name", types="Str"),
        ],
    )
    def get_ip_address():
        """获取本地计算机的IP地址与计算机名"""
        try:
            host_name = socket.gethostname()
            ip_address = socket.gethostbyname(host_name)
            return ip_address, host_name
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DEVICE_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Device",
        inputList=[],
        outputList=[
            atomicMg.param("computer_name", types="Str"),
            atomicMg.param("os_version", types="Str"),
            atomicMg.param("processor", types="Str"),
            atomicMg.param("system_dir", types="Str"),
            atomicMg.param("arch_bits", types="Str"),
        ],
    )
    def get_computer_info():
        """获取计算机信息（名称/操作系统版本/处理器/系统目录/位数）"""
        try:
            computer_name = platform.node() or socket.gethostname()
            os_version = f"{platform.system()} {platform.release()}"
            processor = platform.processor() or platform.machine()
            if sys.platform == "win32":
                system_dir = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or "C:\\Windows"
            else:
                system_dir = os.sep
            arch_bits = platform.architecture()[0] or platform.machine()
            return computer_name, os_version, processor, system_dir, arch_bits
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DEVICE_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Device",
        inputList=[],
        outputList=[],
    )
    def show_desktop():
        """显示桌面（最小化所有窗口）"""
        _require_win32()
        try:
            import win32com.client

            shell = win32com.client.Dispatch("Shell.Application")
            shell.MinimizeAll()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DEVICE_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Device",
        inputList=[
            atomicMg.param(
                "frequency",
                types="Int",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "duration",
                types="Int",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[],
    )
    def play_sound(frequency: int = 1000, duration: int = 500):
        """播放蜂鸣声（频率37-32767赫兹，时长毫秒）"""
        frequency, duration = int(frequency), int(duration)
        if not (37 <= frequency <= 32767):
            raise BaseException(DEVICE_ERROR_FORMAT, f"频率须在 37-32767 赫兹之间: {frequency}")
        if duration <= 0 or duration > 600000:
            raise BaseException(DEVICE_ERROR_FORMAT, f"时长须在 1-600000 毫秒之间: {duration}")
        _require_win32()
        try:
            import winsound

            winsound.Beep(frequency, duration)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DEVICE_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Device",
        inputList=[],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def empty_recycle_bin():
        """清空回收站（不弹确认框）"""
        _require_win32()
        try:
            import ctypes

            # SHERB_NOCONFIRMATION|SHERB_NOPROGRESSUI|SHERB_NOSOUND = 1|2|4
            ret = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
            if ret != 0:  # S_OK = 0（非0表示失败或取消）
                raise BaseException(DEVICE_ERROR_FORMAT, f"SHEmptyRecycleBin 返回码 {ret}")
            return True
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DEVICE_ERROR_FORMAT, str(e))
