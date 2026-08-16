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


class ElementSelectTypeFlag(Enum):
    """下拉框选择方式枚举"""

    BY_TEXT = "byText"  # 按选项内容选择
    BY_INDEX = "byIndex"  # 按选项位置选择（从1开始）


class ElementCheckedTypeFlag(Enum):
    """复选框操作枚举"""

    CHECK = "check"  # 勾选
    UNCHECK = "uncheck"  # 取消勾选
    TOGGLE = "toggle"  # 反选


class ElementWaitTypeFlag(Enum):
    """等待元素状态枚举"""

    APPEAR = "appear"  # 等待元素出现
    DISAPPEAR = "disappear"  # 等待元素消失


class ElementInfoTypeFlag(Enum):
    """元素信息类型枚举"""

    TEXT = "text"  # 获取元素文本内容
    VALUE = "value"  # 获取元素值
    ATTRIBUTE = "attribute"  # 获取元素属性


class RelativeTypeFlag(Enum):
    """关联元素方式枚举"""

    PARENT = "parent"  # 父元素
    FIRST_CHILD = "firstChild"  # 第一个子元素
    NEXT_SIBLING = "nextSibling"  # 下一个同级元素
    PREV_SIBLING = "prevSibling"  # 上一个同级元素


class PositionRelativeToFlag(Enum):
    """元素位置参照枚举"""

    SCREEN = "screen"  # 相对屏幕左上角
    WINDOW = "window"  # 相对元素所在窗口左上角


class DragTypeFlag(Enum):
    """拖拽方式枚举"""

    TO_ELEMENT = "toElement"  # 拖拽至目标元素上
    TO_OFFSET = "toOffset"  # 拖拽至目标点（偏移量）
