from abc import ABC, abstractmethod
from typing import Any

from astronverse.actionlib.types import WinPick
from astronverse.window import ControlInfo, WindowInfoTypeFlag, WindowVisibleTypeFlag, WindowSizeType


class IWindowsCore(ABC):
    @staticmethod
    @abstractmethod
    def find(pick: WinPick) -> Any:
        pass

    @staticmethod
    @abstractmethod
    def top(handler: Any):
        pass

    @staticmethod
    @abstractmethod
    def is_active(handler: Any) -> bool:
        """判断窗口是否为前台激活窗口"""
        pass

    @staticmethod
    @abstractmethod
    def info(handler: Any) -> ControlInfo:
        """窗口信息"""
        pass

    @staticmethod
    @abstractmethod
    def close(handler: Any):
        """关闭窗口"""
        pass

    @staticmethod
    @abstractmethod
    def size(
        handler: Any,
        size_type: WindowSizeType = WindowSizeType.MAX,
        width: int = 0,
        height: int = 0,
    ):
        """设置尺寸"""
        pass

    @staticmethod
    @abstractmethod
    def toControl(handler: Any) -> Any:
        """转换成Control"""
        pass

    @staticmethod
    @abstractmethod
    def find_list(title_contains: str = "") -> list[tuple[str, str]]:
        """按标题包含匹配枚举窗口，返回 (标题, 类名) 列表"""
        pass

    @staticmethod
    @abstractmethod
    def info_value(handler: Any, info_type: WindowInfoTypeFlag) -> Any:
        """按类型获取窗口信息（标题/类名/进程名/位置）"""
        pass

    @staticmethod
    @abstractmethod
    def move(handler: Any, x: int, y: int):
        """移动窗口位置"""
        pass

    @staticmethod
    @abstractmethod
    def set_visible(handler: Any, visible_type: WindowVisibleTypeFlag):
        """设置窗口显示/隐藏"""
        pass

    @staticmethod
    @abstractmethod
    def get_selected_text() -> str:
        """获取当前激活窗口中被选中的文本"""
        pass


class IUITreeCore(ABC):
    @staticmethod
    @abstractmethod
    def GetRootControl() -> Any:
        """获取根Control"""
        pass

    @staticmethod
    @abstractmethod
    def WalkControl(control: Any, includeTop: bool = False, maxDepth: int = 0):
        """生成器，Control遍历"""
        pass

    @staticmethod
    @abstractmethod
    def toHandler(control) -> Any:
        """toHandler 转换成HWN"""
        pass

    @staticmethod
    @abstractmethod
    def setAction(control) -> bool:
        pass
