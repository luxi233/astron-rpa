"""
视频处理相关公开枚举类型。
"""

from enum import Enum

from astronverse.video.error import *  # noqa: F403

__all__ = [
    "AudioFormatType",
    "WatermarkPositionType",
]


class AudioFormatType(Enum):
    """提取音频的目标格式枚举。"""

    MP3 = "mp3"
    WAV = "wav"
    AAC = "aac"


class WatermarkPositionType(Enum):
    """水印位置九宫格枚举。"""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
