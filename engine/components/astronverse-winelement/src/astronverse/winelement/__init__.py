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


class WinLoopGetTypeFlag(Enum):
    """窗口相似元素循环操作类型枚举"""

    GetElement = "getElement"  # 获取元素对象
    GetText = "getText"  # 获取元素文本内容
    GetValue = "getValue"  # 获取元素值
    GetAttribute = "getAttribute"  # 获取元素属性
