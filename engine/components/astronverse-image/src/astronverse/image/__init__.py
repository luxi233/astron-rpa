"""
图片/条码处理相关公开枚举类型。
"""

from enum import Enum

__all__ = [
    "BarcodeType",
    "DirectionType",
    "IdPhotoBgColorType",
    "ImageFormatType",
    "QrErrorCorrectionType",
    "WatermarkPositionType",
]


class BarcodeType(Enum):
    """条形码类型枚举。"""

    EAN13 = "ean13"
    CODE128 = "code128"


class QrErrorCorrectionType(Enum):
    """二维码容错等级枚举。"""

    L = "L"
    M = "M"
    Q = "Q"
    H = "H"


class ImageFormatType(Enum):
    """目标图片格式枚举。"""

    PNG = "png"
    JPEG = "jpeg"
    BMP = "bmp"
    WEBP = "webp"


class DirectionType(Enum):
    """拼接方向枚举。"""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class WatermarkPositionType(Enum):
    """水印/叠加位置九宫格枚举。"""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class IdPhotoBgColorType(Enum):
    """证件照底色枚举。"""

    BLUE = "blue"
    RED = "red"
    WHITE = "white"
    CUSTOM = "custom"
