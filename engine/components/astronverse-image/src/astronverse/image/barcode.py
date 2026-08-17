"""条码/二维码生成与识别。"""

import os
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.image import BarcodeType, QrErrorCorrectionType
from astronverse.image.error import (
    FILE_NOT_FOUND_ERROR_FORMAT,
    INVALID_CONTENT_ERROR_FORMAT,
    RECOGNIZE_FAILED_ERROR_FORMAT,
    SAVE_FAILED_ERROR_FORMAT,
    BaseException,
)


def _default_output_path(prefix: str) -> str:
    """默认输出到 ./astron/ 目录（自动创建父目录）。"""
    out_dir = os.path.join(os.getcwd(), "astron")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{prefix}_{int(time.time() * 1000)}.png")


def _normalize_save_path(save_path: str, prefix: str) -> str:
    path = save_path or _default_output_path(prefix)
    parent = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        raise BaseException(SAVE_FAILED_ERROR_FORMAT, str(e))
    return path


def _import_pyzbar():
    """导入 pyzbar；macOS Homebrew(arm64) 下 find_library 找不到 libzbar 时回退常见路径。"""
    import sys

    try:
        from pyzbar import pyzbar

        return pyzbar
    except Exception:
        import ctypes.util

        orig_find = ctypes.util.find_library

        def _patched(name):
            found = orig_find(name)
            if found is None and name == "zbar":
                for p in ("/opt/homebrew/lib/libzbar.dylib", "/usr/local/lib/libzbar.dylib"):
                    if os.path.exists(p):
                        return p
            return found

        ctypes.util.find_library = _patched
        # zbar_library 在模块级绑定了原始 find_library，须清缓存重导入
        for mod in ("pyzbar", "pyzbar.pyzbar", "pyzbar.wrapper", "pyzbar.zbar_library"):
            sys.modules.pop(mod, None)
        try:
            from pyzbar import pyzbar

            return pyzbar
        finally:
            ctypes.util.find_library = orig_find


class Barcode:
    """条码/二维码原子能力集合。"""

    @staticmethod
    @atomicMg.atomic(
        "Barcode",
        inputList=[
            atomicMg.param("content", types="Str"),
            atomicMg.param("size", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
            ),
        ],
        outputList=[atomicMg.param("qrcode_path", types="Str")],
    )
    def create_qrcode(
        content: str,
        size: int = 300,
        error_correction: QrErrorCorrectionType = QrErrorCorrectionType.M,
        save_path: str = "",
    ):
        """生成二维码图片并保存，返回图片路径。size 为目标边长像素（自动换算模块大小）。"""
        import qrcode

        if not content or not str(content).strip():
            raise BaseException(INVALID_CONTENT_ERROR_FORMAT, "二维码内容不能为空")
        size = max(int(size or 300), 60)
        ec_map = {
            QrErrorCorrectionType.L: qrcode.constants.ERROR_CORRECT_L,
            QrErrorCorrectionType.M: qrcode.constants.ERROR_CORRECT_M,
            QrErrorCorrectionType.Q: qrcode.constants.ERROR_CORRECT_Q,
            QrErrorCorrectionType.H: qrcode.constants.ERROR_CORRECT_H,
        }
        qr = qrcode.QRCode(version=None, error_correction=ec_map[error_correction], box_size=10, border=2)
        qr.add_data(str(content))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        if img.size[0] != size:
            img = img.resize((size, size))
        path = _normalize_save_path(save_path, "qrcode")
        try:
            img.save(path)
        except OSError as e:
            raise BaseException(SAVE_FAILED_ERROR_FORMAT, str(e))
        return path

    @staticmethod
    @atomicMg.atomic(
        "Barcode",
        inputList=[
            atomicMg.param("content", types="Str"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
            ),
        ],
        outputList=[atomicMg.param("barcode_path", types="Str")],
    )
    def create_barcode(
        content: str,
        barcode_type: BarcodeType = BarcodeType.CODE128,
        save_path: str = "",
    ):
        """生成条形码图片（EAN13/CODE128）并保存，返回图片路径。EAN13 内容须为12-13位数字。"""
        import barcode as barcode_lib
        from barcode.writer import ImageWriter

        if not content or not str(content).strip():
            raise BaseException(INVALID_CONTENT_ERROR_FORMAT, "条形码内容不能为空")
        content = str(content).strip()
        if barcode_type == BarcodeType.EAN13 and not (content.isdigit() and len(content) in (12, 13)):
            raise BaseException(INVALID_CONTENT_ERROR_FORMAT, "EAN13条形码内容须为12或13位数字")
        try:
            cls = barcode_lib.get_barcode_class(barcode_type.value)
            code = cls(content, writer=ImageWriter())
            path = _normalize_save_path(save_path, "barcode")
            # python-barcode 自带 .png 扩展名处理：save 返回完整路径
            saved = code.save(os.path.splitext(path)[0])
            if saved != path:
                if os.path.exists(saved) and saved != path:
                    os.replace(saved, path)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SAVE_FAILED_ERROR_FORMAT, str(e))
        return path

    @staticmethod
    @atomicMg.atomic(
        "Barcode",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
            ),
        ],
        outputList=[atomicMg.param("recognize_results", types="List")],
    )
    def recognize_code(image_path: str):
        """识别图片中的二维码/条形码，输出结果列表（每项含 类型/内容 两个字段），未识别到返回空列表。"""
        from PIL import Image

        if not image_path or not os.path.exists(image_path):
            raise BaseException(FILE_NOT_FOUND_ERROR_FORMAT, str(image_path))
        try:
            pyzbar = _import_pyzbar()
        except Exception as e:  # 缺少系统 zbar 库
            raise BaseException(RECOGNIZE_FAILED_ERROR_FORMAT, f"识别组件不可用(缺少zbar系统库): {e}")
        try:
            with Image.open(image_path) as img:
                decoded = pyzbar.decode(img.convert("RGB"))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(RECOGNIZE_FAILED_ERROR_FORMAT, str(e))
        results = [{"类型": d.type, "内容": d.data.decode("utf-8", errors="replace")} for d in decoded]
        return results
