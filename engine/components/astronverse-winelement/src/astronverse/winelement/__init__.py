from enum import Enum


class MouseClickButton(Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class MouseClickType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"


class MouseClickKeyboard(Enum):
    NONE = "none"
    ALT = "alt"
    CTRL = "ctrl"
    SHIFT = "shift"
    WIN = "win"


class ElementInputType(Enum):
    KEYBOARD = "keyboard"
    CLIPBOARD = "clipboard"
    Credential = "credential"


class GetInfoType(Enum):
    TEXT = "text"
    VALUE = "value"
    RECT = "rect"


class ElementContainTypeFlag(Enum):
    """窗口元素包含判断枚举"""

    CONTAIN = "contain"  # 包含
    NOT_CONTAIN = "notcontain"  # 不包含
