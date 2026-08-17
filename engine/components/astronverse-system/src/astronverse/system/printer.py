import sys

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.system import *
from astronverse.system.error import *


def _get_printer_core():
    """获取打印核心（仅 Windows 可用）。"""
    if sys.platform != "win32":
        raise BaseException(PRINTER_NOT_SUPPORTED_FORMAT, "当前系统非 Windows")
    from astronverse.system.core.printer_core import PrinterCore

    return PrinterCore()


def _check_printer_exists(printer_name: str):
    """校验打印机名称是否在已安装列表中。"""
    core = _get_printer_core()
    all_printers = core.view_printer()
    if printer_name not in all_printers:
        raise BaseException(PRINTER_NOT_FOUND_FORMAT.format(printer_name), f"已安装打印机: {all_printers}")
    return core


class Printer:
    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[],
        outputList=[atomicMg.param("printer_list", types="List")],
    )
    def get_printer_list():
        """获取所有打印机列表"""
        core = _get_printer_core()
        try:
            return core.view_printer()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[],
        outputList=[atomicMg.param("printer_name", types="Str")],
    )
    def get_default_printer():
        """获取默认打印机名称"""
        core = _get_printer_core()
        try:
            return core.get_default_printer_name()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[
            atomicMg.param(
                "printer_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def set_default_printer(printer_name: str = ""):
        """设置默认打印机"""
        printer_name = (printer_name or "").strip()
        if not printer_name:
            raise BaseException(PRINTER_ERROR_FORMAT, "打印机名称不能为空")
        core = _check_printer_exists(printer_name)
        try:
            return core.set_default_printer_name(printer_name)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[
            atomicMg.param(
                "printer_name",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[
            atomicMg.param("status_code", types="Int"),
            atomicMg.param("status_text", types="Str"),
        ],
    )
    def get_printer_status(printer_name: str = ""):
        """获取打印机状态（名称为空时取默认打印机）"""
        core = _get_printer_core()
        try:
            status = core.get_printer_status_by_name(printer_name)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))
        return status["status_code"], status["status_text"]

    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[
            atomicMg.param(
                "printer_name",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[atomicMg.param("job_list", types="List")],
    )
    def get_printer_jobs(printer_name: str = ""):
        """获取打印机工作队列（名称为空时取默认打印机）"""
        core = _get_printer_core()
        try:
            return core.get_printer_jobs_by_name(printer_name)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Printer",
        inputList=[
            atomicMg.param(
                "printer_name",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
        ],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def clear_printer_jobs(printer_name: str = ""):
        """清空打印机队列中所有打印作业（名称为空时取默认打印机）"""
        core = _get_printer_core()
        try:
            return core.clear_printer_jobs_by_name(printer_name)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PRINTER_ERROR_FORMAT, str(e))
