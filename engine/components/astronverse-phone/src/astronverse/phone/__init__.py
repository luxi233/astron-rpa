from enum import Enum


class ConnectTargetType(Enum):
    """连接对象: 指定手机/运行时自动选择/所有已连接手机"""

    SPECIFIED = "specified"
    AUTO = "auto"
    ALL = "all"


class ConnectMode(Enum):
    """连接模式: Uiautomator2直连/Appium服务"""

    UIAUTOMATOR2 = "uiautomator2"
    APPIUM = "appium"


class UnlockType(Enum):
    """解锁方式: 无/数字密码/图案密码"""

    NONE = "none"
    PASSWORD = "password"
    PATTERN = "pattern"


class ClickType(Enum):
    """点击方式: 单击/双击/长按/按下/抬起"""

    SINGLE = "single"
    DOUBLE = "double"
    LONG = "long"
    DOWN = "down"
    UP = "up"


class PositionType(Enum):
    """点击位置: 通过坐标指定/通过图像匹配"""

    COORD = "coord"
    IMAGE = "image"


class ImageTargetPart(Enum):
    """目标图像部位: 中心点/随机位置/自定义"""

    CENTER = "center"
    RANDOM = "random"
    CUSTOM = "custom"


class InputTargetType(Enum):
    """输入对象: 光标所在位置/指定输入框"""

    CURSOR = "cursor"
    ELEMENT = "element"


class WaitType(Enum):
    """等待方式: 出现/消失"""

    APPEAR = "appear"
    DISAPPEAR = "disappear"


class SwipeMode(Enum):
    """滑动方式: 方向/坐标"""

    DIRECTION = "direction"
    COORD = "coord"


class SwipeDirection(Enum):
    """滑动方向: 上/下/左/右"""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class KeyType(Enum):
    """按键: 主页/后退/切换应用/回车确认"""

    HOME = "home"
    BACK = "back"
    SWITCH_APP = "switch_app"
    ENTER = "enter"


class LocatorType(Enum):
    """定位方式: id/text/text_contains/description/xpath/selector/class"""

    ID = "id"
    TEXT = "text"
    TEXT_CONTAINS = "text_contains"
    DESCRIPTION = "description"
    XPATH = "xpath"
    SELECTOR = "selector"
    CLASS = "class"


class ElementInfoType(Enum):
    """元素信息: 文本内容/属性值"""

    TEXT = "text"
    ATTRIBUTE = "attribute"


class AppActionType(Enum):
    """App操作: 打开/关闭"""

    OPEN = "open"
    CLOSE = "close"


class OrientationType(Enum):
    """屏幕方向: 竖屏/横屏"""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ScreenActionType(Enum):
    """屏幕操作: 锁定/解锁"""

    LOCK = "lock"
    UNLOCK = "unlock"


class SwipeAreaType(Enum):
    """滑动区域: 整个屏幕/指定元素内"""

    SCREEN = "screen"
    ELEMENT = "element"


class ListSortType(Enum):
    """列表排序: 名称升序/名称降序"""

    ASC = "asc"
    DESC = "desc"
