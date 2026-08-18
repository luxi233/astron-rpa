import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("win32com")  # gui_mouse 间接依赖 win32com（win32gui），仅 Windows 可用

from unittest import TestCase

from astronverse.input import KeyboardType
from astronverse.input.gui_mouse import GuiMouse, Mouse


class TestMouse(TestCase):
    def test_position(self):
        print(Mouse.position())

    def test_mouse_position(self):
        print(GuiMouse.mouse_position())

    def test_move(self):
        Mouse.move(233, 233, 0.1)


class TestKeyboard(TestCase):
    @unittest.skip("keyboard 能力已重构，GuiMouse 无 keyboard 方法")
    def test_input(self):
        gui = GuiMouse()
        gui.keyboard(keyboard_type=KeyboardType.CLIP)
