from dataclasses import dataclass
from enum import Enum
from typing import Any


class WindowSizeType(Enum):
    CUSTOM = "custom"
    MAX = "max"
    MIN = "min"


class WindowExistType(Enum):
    EXIST = "exist"
    NOT_EXIST = "not_exist"
    ACTIVE = "active"
    NOT_ACTIVE = "not_active"


class WindowInfoTypeFlag(Enum):
    """窗口信息类型枚举"""

    TITLE = "title"  # 窗口标题
    CLASS_NAME = "className"  # 窗口类名
    PROCESS_NAME = "processName"  # 进程名
    RECT = "rect"  # 窗口位置尺寸 [left, top, right, bottom]


class WindowVisibleTypeFlag(Enum):
    """窗口可见性枚举"""

    SHOW = "show"  # 显示窗口
    HIDE = "hide"  # 隐藏窗口


@dataclass
class ControlInfo:
    name: str
    classname: str
    position: Any
    handler: Any


@dataclass
class WalkControlInfo:
    name: str
    classname: str
    position: Any
    control: Any
    depth: int
    control_type: Any
    control_type_name: str
    automation_id: str
