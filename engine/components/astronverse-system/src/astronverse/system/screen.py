import sys

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.system import *
from astronverse.system.error import *


def _require_win32():
    if sys.platform != "win32":
        raise BaseException(SCREEN_NOT_SUPPORTED_FORMAT, "当前系统非 Windows")


# 缩放百分比 → LogPixels 注册表值
_SCALE_STEPS = {
    100: 96,
    125: 120,
    150: 144,
    175: 168,
    200: 192,
    225: 216,
    250: 240,
    300: 288,
    350: 336,
    400: 384,
    450: 432,
    500: 480,
}


class Screen:
    @staticmethod
    @atomicMg.atomic(
        "Screen",
        inputList=[],
        outputList=[
            atomicMg.param("width", types="Int"),
            atomicMg.param("height", types="Int"),
            atomicMg.param("scale", types="Int"),
        ],
    )
    def get_screen_resolution():
        """获取屏幕分辨率（物理像素宽高）与缩放百分比"""
        _require_win32()
        import ctypes

        try:
            user32 = ctypes.windll.user32

            # ENUM_CURRENT_SETTINGS = -1
            class DEVMODE(ctypes.Structure):
                _fields_ = [
                    ("dmDeviceName", ctypes.c_wchar * 32),
                    ("dmSpecVersion", ctypes.c_ushort),
                    ("dmDriverVersion", ctypes.c_ushort),
                    ("dmSize", ctypes.c_ushort),
                    ("dmDriverExtra", ctypes.c_ushort),
                    ("dmFields", ctypes.c_ulong),
                    ("dmPositionX", ctypes.c_long),
                    ("dmPositionY", ctypes.c_long),
                    ("dmDisplayOrientation", ctypes.c_ulong),
                    ("dmDisplayFixedOutput", ctypes.c_ulong),
                    ("dmColor", ctypes.c_ushort),
                    ("dmDuplex", ctypes.c_ushort),
                    ("dmYResolution", ctypes.c_ushort),
                    ("dmTTOption", ctypes.c_ushort),
                    ("dmCollate", ctypes.c_ushort),
                    ("dmFormName", ctypes.c_wchar * 32),
                    ("dmLogPixels", ctypes.c_ushort),
                    ("dmBitsPerPel", ctypes.c_ulong),
                    ("dmPelsWidth", ctypes.c_ulong),
                    ("dmPelsHeight", ctypes.c_ulong),
                    ("dmDisplayFlags", ctypes.c_ulong),
                    ("dmDisplayFrequency", ctypes.c_ulong),
                ]

            dm = DEVMODE()
            dm.dmSize = ctypes.sizeof(DEVMODE)
            if not user32.EnumDisplaySettingsW(None, 0xFFFFFFFF, ctypes.byref(dm)):
                raise BaseException(SCREEN_ERROR_FORMAT, "EnumDisplaySettings 获取失败")
            width, height = int(dm.dmPelsWidth), int(dm.dmPelsHeight)

            # 缩放比: 屏幕 DC 的 LOGPIXELSX(88) / 96
            gdi32 = ctypes.windll.gdi32
            hdc = user32.GetDC(0)
            try:
                dpi = gdi32.GetDeviceCaps(hdc, 88)
            finally:
                user32.ReleaseDC(0, hdc)
            scale = int(round(dpi * 100 / 96)) if dpi else 100
            return width, height, scale
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREEN_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Screen",
        inputList=[
            atomicMg.param(
                "width",
                types="Int",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "height",
                types="Int",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "color_bits",
                types="Int",
                required=False,
            ),
        ],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def set_screen_resolution(width: int = 0, height: int = 0, color_bits: int = 32):
        """设置主屏幕分辨率（宽/高像素，颜色位数默认32位）"""
        width, height, color_bits = int(width), int(height), int(color_bits or 32)
        if width < 200 or width > 16384 or height < 200 or height > 16384:
            raise BaseException(SCREEN_ERROR_FORMAT, f"分辨率参数有误: {width}x{height}")
        _require_win32()
        import ctypes

        try:
            user32 = ctypes.windll.user32

            class DEVMODE(ctypes.Structure):
                _fields_ = [
                    ("dmDeviceName", ctypes.c_wchar * 32),
                    ("dmSpecVersion", ctypes.c_ushort),
                    ("dmDriverVersion", ctypes.c_ushort),
                    ("dmSize", ctypes.c_ushort),
                    ("dmDriverExtra", ctypes.c_ushort),
                    ("dmFields", ctypes.c_ulong),
                    ("dmPositionX", ctypes.c_long),
                    ("dmPositionY", ctypes.c_long),
                    ("dmDisplayOrientation", ctypes.c_ulong),
                    ("dmDisplayFixedOutput", ctypes.c_ulong),
                    ("dmColor", ctypes.c_ushort),
                    ("dmDuplex", ctypes.c_ushort),
                    ("dmYResolution", ctypes.c_ushort),
                    ("dmTTOption", ctypes.c_ushort),
                    ("dmCollate", ctypes.c_ushort),
                    ("dmFormName", ctypes.c_wchar * 32),
                    ("dmLogPixels", ctypes.c_ushort),
                    ("dmBitsPerPel", ctypes.c_ulong),
                    ("dmPelsWidth", ctypes.c_ulong),
                    ("dmPelsHeight", ctypes.c_ulong),
                    ("dmDisplayFlags", ctypes.c_ulong),
                    ("dmDisplayFrequency", ctypes.c_ulong),
                ]

            dm = DEVMODE()
            dm.dmSize = ctypes.sizeof(DEVMODE)
            # 取当前设置作为基底(保留刷新率等)
            user32.EnumDisplaySettingsW(None, 0xFFFFFFFF, ctypes.byref(dm))
            dm.dmPelsWidth = width
            dm.dmPelsHeight = height
            dm.dmBitsPerPel = color_bits
            # DM_PELSWIDTH|DM_PELSHEIGHT|DM_BITSPERPEL = 0x80000|0x100000|0x40000
            dm.dmFields = 0x1C0000
            ret = user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
            if ret != 0:  # DISP_CHANGE_SUCCESSFUL = 0
                raise BaseException(SCREEN_ERROR_FORMAT, f"ChangeDisplaySettings 返回码 {ret}（分辨率可能不受支持）")
            return True
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREEN_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "Screen",
        inputList=[
            atomicMg.param(
                "scale",
                types="Int",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def set_screen_scale(scale: int = 100):
        """设置系统缩放百分比（100-500，步进25），注销后生效"""
        scale = int(scale)
        if scale < 100 or scale > 500 or scale % 25 != 0:
            raise BaseException(SCREEN_ERROR_FORMAT, "缩放百分比须为 100-500 之间且为 25 的倍数")
        _require_win32()
        import winreg

        log_pixels = _SCALE_STEPS.get(scale, int(96 * scale / 100))
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
            try:
                winreg.SetValueEx(key, "Win8DpiScale", 0, winreg.REG_SZ, "1")
                winreg.SetValueEx(key, "LogPixels", 0, winreg.REG_DWORD, log_pixels)
            finally:
                winreg.CloseKey(key)
            return True
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREEN_ERROR_FORMAT, f"注册表写入失败: {e}")
