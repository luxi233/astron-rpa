import threading
import time

import pythoncom
import pyWinhook as pyWinhook
import win32api
from astronverse.picker import IEventCore, MKSign
from astronverse.picker.logger import logger
from pyWinhook import KeyboardEvent

# VK_LCONTROL(0xA2) / VK_RCONTROL(0xA3)
_CTRL_VKS = (0xA2, 0xA3)
# 钩子事件名: 左/右Ctrl(不同键盘布局/远程桌面下命名可能差异,两者都认)
_CTRL_KEY_NAMES = ("Lcontrol", "Rcontrol")


class EventCore(IEventCore):
    """用户键盘鼠标事件"""

    def __init__(self):
        self.__hook_manager = None
        self.__closed = True
        self.__control_down = False
        # 下面两个点击后 有一定的等待能力
        self.__esc = False
        self.__control_left_down = False
        self.__init = False
        # 新增的标志位
        self.__f4_pressed = False  # F4键按下标志
        # 键鼠启动的上层应用
        self.domain = None

    def __mouse_left_down__(self, event):
        # 鼠标按下瞬间查询真实Ctrl状态(左/右都认),不单纯依赖KeyDown事件追踪——
        # 修复: 1)右Ctrl按下时事件名是Rcontrol,原逻辑只认Lcontrol导致点击穿透到目标应用;
        #       2)捕获开始前Ctrl已按住时钩子收不到KeyDown,追踪状态为False同样穿透
        ctrl_down = self.__control_down or any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in _CTRL_VKS)
        if ctrl_down:
            self.__control_left_down = True
            return False
        return True

    def __key_pressed__(self, event: KeyboardEvent):
        if event.Key in _CTRL_KEY_NAMES:
            self.__control_down = True
        elif event.Key == "F4":
            self.__f4_pressed = True
        return True

    def __key_released__(self, event: KeyboardEvent):
        if event.Key == "Escape":
            self.__esc = True
        if event.Key in _CTRL_KEY_NAMES:
            self.__control_down = False
        return True

    def __un_hook__(self):
        if self.__hook_manager is None:
            return
        self.__hook_manager.UnhookMouse()
        self.__hook_manager.UnhookKeyboard()
        self.__hook_manager = None

        logger.info("EventCore __un_hook__")

    def __hook__(self):
        logger.info("EventCore __hook__ start")
        self.__hook_manager = pyWinhook.HookManager()
        self.__hook_manager.MouseLeftDown = self.__mouse_left_down__
        self.__hook_manager.KeyDown = self.__key_pressed__
        self.__hook_manager.KeyUp = self.__key_released__
        self.__hook_manager.HookMouse()
        self.__hook_manager.HookKeyboard()
        self.__init = True
        pythoncom.PumpMessages()
        logger.info("EventCore __hook__ end")

    def is_cancel(self):
        return self.__esc

    def is_focus(self):
        return self.__control_left_down

    def is_f4_pressed(self):
        """检查F4键是否按下"""
        return self.__f4_pressed

    def reset_f4_flag(self):
        """重置F4键标志位"""
        self.__f4_pressed = False

    def reset_cancel_flag(self):
        """重置ESC取消标志位"""
        self.__esc = False

    def start(self, domain=MKSign.PICKER):
        if not self.__closed:
            return False

        logger.info("EventCore start")
        self.__init = False

        # 独立线程启动鼠标和键盘hook
        threading.Thread(target=self.__hook__, args=(), daemon=True).start()
        self.__control_down = False
        self.__control_left_down = False
        self.__esc = False
        self.__f4_pressed = False
        self.__closed = False

        while not self.__init:
            time.sleep(0.01)
        self.domain = domain
        return True

    def close(self):
        if self.__closed:
            return False

        logger.info("EventCore close")
        self.__un_hook__()
        self.__control_down = False
        self.__control_left_down = False
        self.__esc = False
        self.__f4_pressed = False
        self.__closed = True
        self.domain = None
        return True
