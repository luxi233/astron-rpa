import os
import re
import subprocess
import sys
import time

import pyautogui
from astronverse.baseline.logger.logger import logger
from pynput.keyboard import Controller

language_map = {0x0409: "xkb:us::eng", 0x0804: "zh_CN"}  # 英文  # 中文


class Keyboard:
    def __init__(self):
        pyautogui.FAILSAFE = False

    @staticmethod
    def change_language(language: int):
        if sys.platform == "win32":
            import win32api
            import win32gui
            from win32con import WM_INPUTLANGCHANGEREQUEST

            hwnd = win32gui.GetForegroundWindow()
            im_list = win32api.GetKeyboardLayoutList()
            im_list = list(map(hex, im_list))
            win32api.SendMessage(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, language)
        else:
            try:
                # 先查询当前输入法状态
                result = subprocess.run(
                    ["fcitx-remote"],
                    timeout=5,
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                )
                if result.returncode != 0:
                    logger.info("无法查询fcitx状态，可能fcitx未运行")
                    return

                current_status = int(result.stdout.strip())
                logger.info(f"当前输入法状态: {current_status}")

                # 根据language参数确定期望状态
                if language == 0x0409:  # 英文 - 期望状态为1（未激活）
                    expected_status = 1
                elif language == 0x0804:  # 中文 - 期望状态为2（激活）
                    expected_status = 2
                else:
                    logger.info(f"不支持的语言代码: {hex(language)}")
                    return

                # 判断是否需要切换
                if current_status != expected_status:
                    logger.info(f"需要切换输入法：从状态{current_status}切换到状态{expected_status}")
                    # 执行切换命令
                    subprocess.run(
                        ["fcitx-remote", "-t"],
                        timeout=5,
                        check=False,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                (logger.info(f"切换输入法时发生错误: {e}"))

    @staticmethod
    def write_char(char: str):
        """
        键盘写字符
        keyboard.type()在输入法英文状态下可同时输入中英文字符
        """
        keyboard = Controller()
        return keyboard.type(char)

    @staticmethod
    def write_unicode(text: str, delay: float = 0):
        """
        使用 Windows API 输入 Unicode 文本
        支持中英文、emoji等所有Unicode字符，不依赖输入法状态

        Args:
            text: 要输入的文本
            delay: 每个字符之间的延迟（秒），默认0.01秒

        Example:
            Keyboard.write_unicode("Hello世界！😀")
        """
        if sys.platform == "win32":
            from astronverse.input.code.windows_input import type_text

            return type_text(text, delay=delay)
        else:
            # Linux/Mac 回退到 pynput
            keyboard = Controller()
            return keyboard.type(text)

    @staticmethod
    def press(keys, presses: int = 1, interval: float = 0.0):
        """
        敲键
        eg1: pyautogui.press(['left', 'left', 'left'])
        eg2: pyautogui.press('left')
        :param keys: 可以是数组 https://pyautogui.readthedocs.io/en/latest/keyboard.html#keyboard-keys
        """
        return pyautogui.press(keys=keys, presses=presses, interval=interval)

    @staticmethod
    def hotkey(*args, **kwargs):
        """
        热键
        eg: pyautogui.hotkey('ctrl', 'shift', 'esc')
        """
        return pyautogui.hotkey(*args, **kwargs)

    @staticmethod
    def key_down(key):
        """
        按键
        """
        return pyautogui.keyDown(key=key)

    @staticmethod
    def key_up(key):
        """
        松键
        :param key: 键 https://pyautogui.readthedocs.io/en/latest/keyboard.html#keyboard-keys
        :return:
        """
        return pyautogui.keyUp(key=key)

    # 特殊按键语法: 键名映射表 {KEY} -> pyautogui键名
    SPECIAL_KEY_MAP = {
        "ENTER": "enter",
        "TAB": "tab",
        "SPACE": "space",
        "ESC": "escape",
        "ESCAPE": "escape",
        "BACKSPACE": "backspace",
        "BS": "backspace",
        "BACK": "backspace",
        "DEL": "delete",
        "DELETE": "delete",
        "INS": "insert",
        "INSERT": "insert",
        "HOME": "home",
        "END": "end",
        "PGUP": "pgup",
        "PAGEUP": "pgup",
        "PGDN": "pgdn",
        "PAGEDOWN": "pgdn",
        "UP": "up",
        "DOWN": "down",
        "LEFT": "left",
        "RIGHT": "right",
        "PRTSC": "printscreen",
        "PRINTSCREEN": "printscreen",
        "WIN": "win",
        "CTRL": "ctrl",
        "ALT": "alt",
        "SHIFT": "shift",
        "CAPSLOCK": "capslock",
        "NUMLOCK": "numlock",
        "SCROLLLOCK": "scrolllock",
        "APPS": "apps",
        "VOLUMEUP": "volumeup",
        "VOLUMEDOWN": "volumedown",
        "VOLUMEMUTE": "volumemute",
    }

    # 特殊按键语法: 修饰键前缀 ^!+#
    SPECIAL_MODIFIER_PREFIX = {"^": "ctrl", "!": "alt", "+": "shift", "#": "win"}

    @staticmethod
    def _special_dispatch_token(token: str, modifiers: list, interval: float):
        """执行{...}内的特殊按键token"""
        token = token.strip()
        # {ASC nnnn} Alt+数字码输入
        asc_match = re.match(r"^ASC\s+(\d+)$", token)
        if asc_match:
            code = int(asc_match.group(1))
            pyautogui.hotkey("alt", *list(str(code % 100000)))
            time.sleep(interval)
            return
        # {KEY count} 重复按键
        count_match = re.match(r"^([A-Za-z0-9_]+)\s+(\d+)$", token)
        if count_match:
            key_name, count = count_match.group(1), int(count_match.group(2))
            pyautogui_key = Keyboard.SPECIAL_KEY_MAP.get(key_name.upper())
            if pyautogui_key:
                Keyboard._special_press(pyautogui_key, modifiers, count, interval)
                return
        # {KEYDOWN} / {KEYUP} 持续按下/松开
        down_match = re.match(r"^([A-Za-z0-9_]+)DOWN$", token)
        if down_match:
            key_name = down_match.group(1)
            pyautogui_key = Keyboard.SPECIAL_KEY_MAP.get(key_name.upper())
            if pyautogui_key:
                pyautogui.keyDown(pyautogui_key)
                time.sleep(interval)
                return
        up_match = re.match(r"^([A-Za-z0-9_]+)UP$", token)
        if up_match:
            key_name = up_match.group(1)
            pyautogui_key = Keyboard.SPECIAL_KEY_MAP.get(key_name.upper())
            if pyautogui_key:
                pyautogui.keyUp(pyautogui_key)
                time.sleep(interval)
                return
        # 普通 {KEY}
        pyautogui_key = Keyboard.SPECIAL_KEY_MAP.get(token.upper())
        if pyautogui_key:
            Keyboard._special_press(pyautogui_key, modifiers, 1, interval)

    @staticmethod
    def _special_press(pyautogui_key: str, modifiers: list, presses: int, interval: float):
        """带修饰键按键"""
        if modifiers:
            for _ in range(presses):
                pyautogui.hotkey(*modifiers, pyautogui_key)
                time.sleep(interval)
        else:
            pyautogui.press(pyautogui_key, presses=presses, interval=interval if interval > 0 else 0.0)

    @staticmethod
    def write_special(message: str, interval: float = 0.05):
        """
        特殊按键语法输入（影刀/AutoIt风格）
        支持: ^!+#修饰键前缀, {ENTER}/{TAB}/{F1}-{F12}等按键,
              {KEY n}重复n次, {KEYDOWN}/{KEYUP}持续按下/松开, {ASC nnnn}Alt码输入, {{ }}转义
        eg: "hello{ENTER}"  "^c"复制  "{TAB 3}"按3次Tab  "%{F4}"关闭窗口
        """
        i = 0
        n = len(message)
        modifiers = []
        while i < n:
            ch = message[i]
            if ch in Keyboard.SPECIAL_MODIFIER_PREFIX:
                modifiers.append(Keyboard.SPECIAL_MODIFIER_PREFIX[ch])
                i += 1
                continue
            if ch == "{":
                if i + 1 < n and message[i + 1] == "{":
                    Keyboard.write_char("{")
                    modifiers = []
                    i += 2
                    continue
                end = message.find("}", i + 1)
                if end == -1:
                    Keyboard.write_char(ch)
                    i += 1
                    continue
                token = message[i + 1 : end]
                Keyboard._special_dispatch_token(token, modifiers, interval)
                modifiers = []
                i = end + 1
                continue
            # 普通字符: 带修饰键则热键组合, 否则逐字输入
            if modifiers:
                if ch.isalnum() or ch in "!@#$%^&*()_+-=[]{}|;:'\",.<>/?`~":
                    pyautogui.hotkey(*modifiers, ch.lower())
                    time.sleep(interval)
                else:
                    Keyboard.write_char(ch)
                modifiers = []
            else:
                Keyboard.write_char(ch)
            i += 1

    @staticmethod
    def get_drive_path():
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        relative_dir = os.path.join("VK", "bin", "Debug", "VK.exe")
        drive_path = os.path.join(parent_dir, relative_dir)
        return drive_path
