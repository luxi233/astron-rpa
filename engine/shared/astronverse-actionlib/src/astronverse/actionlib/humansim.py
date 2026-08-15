"""模拟真人操作全局上下文

通过 System.human_sim_start（开启模拟真人操作）与 System.human_sim_end（结束模拟真人操作）
控制区间内的桌面鼠标/键盘操作按仿真模式执行：
- 仿真移动鼠标：瞬移调用自动改为带缓动曲线的移动
- 仿真点击元素：点击坐标随机偏移 + 按下/抬起随机间隔
- 仿真操作停顿：每个 GUI 操作前随机停顿 min~max 秒
"""

import random
import time


class HumanSimContext:
    """模拟真人操作上下文（进程级单例）"""

    def __init__(self):
        self.active = False
        self.enable_move = True
        self.enable_click = True
        self.enable_pause = True
        self.min_pause = 0.1
        self.max_pause = 0.5
        self.click_jitter_radius = 3.0

    def start(
        self,
        enable_move: bool = True,
        enable_click: bool = True,
        enable_pause: bool = True,
        min_pause: float = 0.1,
        max_pause: float = 0.5,
    ):
        """开启模拟真人操作"""
        min_pause = float(min_pause)
        max_pause = float(max_pause)
        if min_pause < 0 or max_pause < 0:
            raise ValueError("停顿时长不能为负数")
        if min_pause > max_pause:
            raise ValueError("最小停顿时长{}秒不能大于最大时长{}秒".format(min_pause, max_pause))
        self.enable_move = bool(enable_move)
        self.enable_click = bool(enable_click)
        self.enable_pause = bool(enable_pause)
        self.min_pause = min_pause
        self.max_pause = max_pause
        self.active = True

    def stop(self):
        """结束模拟真人操作"""
        self.active = False

    def should_simulate_move(self) -> bool:
        return self.active and self.enable_move

    def should_jitter_click(self) -> bool:
        return self.active and self.enable_click

    def jitter(self, value: float) -> float:
        """给坐标加随机偏移（模拟真人点击位置不精准）"""
        if not self.should_jitter_click():
            return value
        return value + random.uniform(-self.click_jitter_radius, self.click_jitter_radius)

    def click_interval(self, default_interval: float = 0.0) -> float:
        """给点击的按下/抬起之间加随机间隔"""
        if not self.should_jitter_click():
            return default_interval
        return max(default_interval, random.uniform(0.05, 0.15))

    def pre_action_pause(self):
        """GUI 操作前随机停顿（模拟操作间思考/反应时间）"""
        if not (self.active and self.enable_pause):
            return
        time.sleep(random.uniform(self.min_pause, self.max_pause))


human_sim = HumanSimContext()
