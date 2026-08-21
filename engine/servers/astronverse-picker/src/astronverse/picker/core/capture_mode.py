"""I4 会话内捕获模式切换状态机。

拾取会话进行中(START 已下发, 绘制循环运行中), 支持标准/深度/CV 三种捕获模式互切,
免去"退出重进"。核心机制: PickerServer 绘制循环每轮都会重读会话字典里的 pick_mode
并由 _draw_element 现推导 domain 与 deep 标记, 因此就地改写会话字典的 pick_mode 即可
在下一绘制周期生效(无需重启会话)。

- 标准 <-> 深度: 同属 UIA 拾取引擎, 仅改写 pick_mode, requires_reinit=False, 会话内即时生效。
- CV: 走独立 vision-picker 图像框选通道(与 UIA 会话是两套资源), 会话内切换需先卸载当前
  UIA 会话再重启图像框选, 故 requires_reinit=True, 由上层编排"退出并重进"以正确释放句柄。

该状态机不持有会话字典引用(由调用方传入), 便于单测; 切换历史留痕供排障。
"""

from enum import Enum
from typing import Any, Optional


class CaptureMode(Enum):
    """捕获模式(对齐拾取前下拉三模式)"""

    STANDARD = "standard"  # 标准: 无 pick_mode, domain=AUTO(策略试探择优)
    DEEP = "deep"  # 深度: pick_mode=DeepUIA, 直达 UIA 引擎更大深度下钻
    CV = "cv"  # CV图像: 独立 vision-picker 通道


# mode -> 写入会话字典的 pick_mode 值 / 是否需要重初始化拾取引擎
_MODE_CONFIG = {
    CaptureMode.STANDARD: {"pick_mode": None, "requires_reinit": False},
    CaptureMode.DEEP: {"pick_mode": "DeepUIA", "requires_reinit": False},
    # CV 需卸载 UIA 会话并重启 vision-picker 通道, 避免两套句柄并存泄漏
    CaptureMode.CV: {"pick_mode": "CV", "requires_reinit": True},
}

# 切换时允许清理的模式专属残留键(deep 标记由 _draw_element 按 pick_mode 现推导, 不留旧值)
_MODE_RESIDUE_KEYS = ("deep",)


class CaptureModeManager:
    """捕获模式切换状态机。

    current 记录最近一次显式切换到的模式; None 表示会话尚未发生显式切换
    (沿用拾取前下拉选定的缺省模式)。
    """

    def __init__(self):
        self.current: Optional[CaptureMode] = None
        self.history: list = []

    @staticmethod
    def _resolve(target) -> CaptureMode:
        """归一化目标模式; 非法值抛 ValueError(由上层转为业务错误)"""
        if isinstance(target, CaptureMode):
            return target
        try:
            return CaptureMode(str(target).lower())
        except ValueError:
            valid = ", ".join(m.value for m in CaptureMode)
            raise ValueError(f"未知捕获模式 {target!r}, 可选值: {valid}")

    def switch(self, session_data: dict, target) -> dict:
        """切换会话捕获模式, 就地改写 session_data 并返回切换结果。

        Args:
            session_data: 会话字典(svc.sign()[START] 引用), 绘制循环每轮重读
            target: 目标模式(CaptureMode 或 'standard'/'deep'/'cv')

        Returns:
            {mode, previous, pick_mode, requires_reinit}

        Raises:
            ValueError: 目标模式非法
        """
        mode = self._resolve(target)
        config = _MODE_CONFIG[mode]
        previous = self.current

        # 就地改写 pick_mode: 标准模式移除该键(domain 回落 AUTO), 其余写入对应值
        if config["pick_mode"] is None:
            session_data.pop("pick_mode", None)
        else:
            session_data["pick_mode"] = config["pick_mode"]

        # 清理模式专属残留, 防止上一模式的标记串扰新模式
        for key in _MODE_RESIDUE_KEYS:
            session_data.pop(key, None)

        self.current = mode
        self.history.append((previous.value if previous else None, mode.value))
        return {
            "mode": mode.value,
            "previous": previous.value if previous else None,
            "pick_mode": config["pick_mode"],
            "requires_reinit": config["requires_reinit"],
        }


# 会话级单例: 同一拾取进程内一次只有一个活动会话, 共享切换状态
capture_mode_manager = CaptureModeManager()
