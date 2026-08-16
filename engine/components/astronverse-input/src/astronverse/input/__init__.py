from enum import Enum


class KeyboardType(Enum):
    NORMAL = "normal"
    SPECIAL = "special"
    DRIVER = "driver"
    CLIP = "clip"
    GBLID = "gblid"


class BtnType(Enum):
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"


class BtnModel(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    DOWN = "down"
    UP = "up"


class KeyModel(Enum):
    CLICK = "click"
    DOWN = "down"
    UP = "up"


class ScrollType(Enum):
    TIME = "time"
    PX = "px"


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    # LEFT = "left"
    # RIGHT = "right"


class ControlType(Enum):
    EMPTY = "none"
    CTRL = "ctrl"
    ALT = "alt"
    SHIFT = "shift"
    WIN = "win"
    SPACE = "space"


class WindowType(Enum):
    FULL_SCREEN = "fullscreen"
    ACTIVE_WINDOW = "active_window"
    CURRENT_POSITION = "current_position"


class ClickMoveType(Enum):
    """鼠标点击前移动方式"""

    CURRENT = "current"  # 当前位置点击（不移动）
    SCREEN = "screen"  # 移动到屏幕指定坐标
    ACTIVE_WINDOW = "active_window"  # 移动到激活窗口内指定坐标


class PositionReferenceType(Enum):
    """鼠标位置参照物"""

    SCREEN = "screen"  # 相对屏幕左上角
    ACTIVE_WINDOW = "active_window"  # 相对激活窗口左上角


class Speed(Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class MoveType(Enum):
    LINEAR = "linear"
    SIMULATION = "simulation"
    TELEPORTATION = "teleportation"


class Simulate_flag(Enum):
    YES = "yes"
    NO = "no"
