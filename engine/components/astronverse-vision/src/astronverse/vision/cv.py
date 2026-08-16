import base64
import io
import json
import random
import re
import time
import urllib.request

import pyautogui
from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, AtomicLevel, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import IMGPick
from astronverse.input import ControlType, MoveType, Simulate_flag, Speed
from astronverse.input.code.clipboard import Clipboard
from astronverse.input.code.keyboard import Keyboard
from astronverse.input.code.mouse import Mouse
from astronverse.input.error import *
from astronverse.vision import *
from astronverse.vision.core import CvCore
from astronverse.vision.error import *

# 定义输入法的语言代码
ENGLISH = 0x0409  # 英文（美国）
CHINESE = 0x0804  # 中文（简体，中国）
speed_to_int = {Speed.SLOW: 2, Speed.NORMAL: 1, Speed.FAST: 0.5}


class CV:
    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "input_data",
                formType=AtomicFormTypeMeta(AtomicFormType.PICK.value, params={"use": "CV"}),
                noInput=True,
            ),
            atomicMg.param("btn_type", required=False),
            atomicMg.param("btn_model", required=False),
            atomicMg.param("click_position", required=False),
            atomicMg.param(
                "specified_position",
                required=False,
                formType=AtomicFormTypeMeta(AtomicFormType.GRID.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.specified_position.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "horizontal_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.horizontal_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "vertical_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.vertical_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "wait_time",
                types="Int",
                level=AtomicLevel.ADVANCED.value,
                required=False,
            ),
            atomicMg.param(
                "match_similarity",
                formType=AtomicFormTypeMeta(AtomicFormType.SLIDER.value),
                required=False,
            ),
            atomicMg.param("move_type", level=AtomicLevel.ADVANCED.value, required=False),
            atomicMg.param(
                "move_speed",
                level=AtomicLevel.ADVANCED.value,
                dynamics=[
                    DynamicsItem(
                        key="$this.move_speed.show",
                        expression="return ['{}','{}'].includes($this.move_type.value)".format(
                            MoveType.LINEAR.value, MoveType.SIMULATION.value
                        ),
                    )
                ],
                required=False,
            ),
        ],
        outputList=[],
    )
    def cv_click(
        input_data: IMGPick,
        btn_type: BtnType = BtnType.LEFT,
        btn_model: BtnModel = BtnModel.CLICK,
        click_position: PositionType = PositionType.CENTER,
        specified_position=5,
        horizontal_move: int = 0,
        vertical_move: int = 0,
        match_similarity: float = 0.95,
        move_type: MoveType = MoveType.LINEAR,
        move_speed: Speed = Speed.NORMAL,
        wait_time: int = 10,
    ):
        """
        鼠标点击图片
        :param input_data: 目标图像
        :param btn_type: 鼠标按键
        :param btn_model: 点击方式
        :param click_position: 点击位置
        :param specified_position: 指定位置
        :param horizontal_move: 横向平移
        :param vertical_move: 纵向平移
        :param match_similarity: 匹配相似度
        :param wait_time: 等待时间
        :return: 空
        """
        start_time = time.time()
        while True:
            target_rect = CvCore.match_imgs(input_data=input_data, match_similarity=match_similarity)
            if target_rect is not None:
                try:
                    if click_position == PositionType.CENTER:
                        target_x = target_rect[0] + target_rect[2] // 2
                        target_y = target_rect[1] + target_rect[3] // 2
                    elif click_position == PositionType.RANDOM:
                        target_x = target_rect[0] + random.randint(0, target_rect[2])
                        target_y = target_rect[1] + random.randint(0, target_rect[3])
                    elif click_position == PositionType.SPECIFIC:
                        position = specified_position
                        if position is None:
                            raise BaseException(SPECIFIC_POSITION_ERROR, "未指定点击位置，请检查参数")
                        # 按照指定位置计算点击位置
                        target_x, target_y = CvCore.get_region_position(
                            target_rect, position, horizontal_move, vertical_move
                        )
                    else:
                        raise NotImplementedError()

                    screen_weight, screen_height = Mouse.screen_size()
                    if target_x < 0 or target_x > screen_weight or target_y < 0 or target_y > screen_height:
                        raise BaseException(REGION_ERROR, "坐标参数不合法！")

                    if move_type == MoveType.LINEAR:
                        Mouse.move(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.linear,
                        )
                    elif move_type == MoveType.SIMULATION:
                        Mouse.move_simulate(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.easeInOutQuad,  # type: ignore
                        )
                    elif move_type == MoveType.TELEPORTATION:
                        Mouse.move(target_x, target_y, duration=0)
                    else:
                        raise NotImplementedError()

                    if btn_model == BtnModel.CLICK:
                        Mouse.click(None, None, 1, 0, btn_type.value)
                    elif btn_model == BtnModel.DOUBLE_CLICK:
                        Mouse.click(None, None, 2, 0, btn_type.value)
                    else:
                        raise NotImplementedError()

                    return True
                except Exception as e:
                    raise BaseException(MOUSE_CLICK_ERROR, "鼠标点击失败")
            else:
                if time.time() - start_time > wait_time:
                    break
                else:
                    time.sleep(0.1)

        raise BaseException(CV_MATCH_ERROR, "超时未匹配到目标元素，请检查当前界面或降低匹配相似度重试")

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "input_data",
                formType=AtomicFormTypeMeta(AtomicFormType.PICK.value, params={"use": "CV"}),
                noInput=True,
            ),
            atomicMg.param("click_position", required=False),
            atomicMg.param(
                "specified_position",
                formType=AtomicFormTypeMeta(AtomicFormType.GRID.value),
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.specified_position.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "horizontal_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.horizontal_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "vertical_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.vertical_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "match_similarity",
                formType=AtomicFormTypeMeta(AtomicFormType.SLIDER.value),
                required=False,
            ),
            atomicMg.param(
                "wait_time",
                types="Int",
                level=AtomicLevel.ADVANCED.value,
                required=False,
            ),
            atomicMg.param("move_type", level=AtomicLevel.ADVANCED.value, required=False),
            atomicMg.param(
                "move_speed",
                level=AtomicLevel.ADVANCED.value,
                dynamics=[
                    DynamicsItem(
                        key="$this.move_speed.show",
                        expression="return ['{}','{}'].includes($this.move_type.value)".format(
                            MoveType.LINEAR.value, MoveType.SIMULATION.value
                        ),
                    )
                ],
                required=False,
            ),
        ],
        outputList=[],
    )
    def hover_image(
        input_data: IMGPick,
        click_position: PositionType = PositionType.CENTER,
        specified_position=5,
        horizontal_move: int = 0,
        vertical_move: int = 0,
        match_similarity: float = 0.95,
        move_type: MoveType = MoveType.LINEAR,
        move_speed: Speed = Speed.NORMAL,
        wait_time: int = 10,
    ):
        """
        鼠标悬浮在图像上
        :param input_data: 目标图像
        :param click_position: 点击位置
        :param specified_position: 指定位置
        :param horizontal_move: 横向平移
        :param vertical_move: 纵向平移
        :param match_similarity: 匹配相似度
        :param wait_time: 等待时间
        :return: 空
        """
        start_time = time.time()
        while True:
            target_rect = CvCore.match_imgs(input_data, match_similarity)
            if target_rect is not None:
                try:
                    if click_position == PositionType.CENTER:
                        target_x = target_rect[0] + target_rect[2] // 2
                        target_y = target_rect[1] + target_rect[3] // 2
                    elif click_position == PositionType.RANDOM:
                        target_x = target_rect[0] + random.randint(0, target_rect[2])
                        target_y = target_rect[1] + random.randint(0, target_rect[3])
                    elif click_position == PositionType.SPECIFIC:
                        position = specified_position
                        if position is None:
                            raise BaseException(SPECIFIC_POSITION_ERROR, "未指定点击位置，请检查参数")
                        # 按照指定位置计算点击位置
                        target_x, target_y = CvCore.get_region_position(
                            target_rect, position, horizontal_move, vertical_move
                        )
                    else:
                        raise NotImplementedError()

                    screen_weight, screen_height = Mouse.screen_size()
                    if target_x < 0 or target_x > screen_weight or target_y < 0 or target_y > screen_height:
                        raise BaseException(REGION_ERROR, "坐标参数不合法！")

                    if move_type == MoveType.LINEAR:
                        Mouse.move(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.linear,
                        )
                    elif move_type == MoveType.SIMULATION:
                        Mouse.move_simulate(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.easeInOutQuad,  # type: ignore
                        )
                    elif move_type == MoveType.TELEPORTATION:
                        Mouse.move(target_x, target_y, duration=0)
                    else:
                        raise NotImplementedError()

                    return True
                except Exception as e:
                    raise BaseException(MOUSE_HOVER_ERROR, "鼠标悬停失败")
            else:
                if time.time() - start_time > wait_time:
                    break
                else:
                    time.sleep(0.1)

        raise BaseException(CV_MATCH_ERROR, "超时未匹配到目标元素，请检查当前界面或降低匹配相似度重试")

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "input_data",
                formType=AtomicFormTypeMeta(AtomicFormType.PICK.value, params={"use": "CV"}),
                noInput=True,
            ),
            atomicMg.param("exist_type", required=False),
            atomicMg.param(
                "match_similarity",
                formType=AtomicFormTypeMeta(AtomicFormType.SLIDER.value),
                required=False,
            ),
            atomicMg.param(
                "wait_time",
                types="Int",
                level=AtomicLevel.ADVANCED.value,
                required=False,
            ),
        ],
    )
    def is_image_exist(
        input_data: IMGPick,
        exist_type: ExistType = ExistType.EXIST,
        match_similarity: float = 0.95,
        wait_time: int = 10,
    ):
        """
        判断图像是否存在
        :param input_data: 目标图像
        :param exist_type: 判断类型
        :param match_similarity: 匹配相似度
        :param wait_time: 等待时间
        :return: 图像是否存在的结果
        """
        start_time = time.time()

        while True:
            target_rect = CvCore.match_imgs(input_data, match_similarity)

            if exist_type == ExistType.EXIST:
                if target_rect is not None:
                    return True
            elif exist_type == ExistType.NOT_EXIST:
                if target_rect is None:
                    return True
            else:
                raise NotImplementedError()

            if time.time() - start_time > wait_time:
                break

            time.sleep(0.5)

        return False

    # @staticmethod
    # @atomicMg.atomic("CV")
    # def is_image_exist_end():
    #     pass

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "input_data",
                formType=AtomicFormTypeMeta(AtomicFormType.PICK.value, params={"use": "CV"}),
                noInput=True,
            ),
            atomicMg.param("wait_type", required=False),
            atomicMg.param("wait_time", types="Int", required=False),
            atomicMg.param(
                "match_similarity",
                formType=AtomicFormTypeMeta(AtomicFormType.SLIDER.value),
                required=False,
            ),
        ],
        outputList=[atomicMg.param("image_wait_result", types="Bool")],
    )
    def wait_image(
        input_data: IMGPick,
        wait_type: WaitType = WaitType.APPEAR,
        wait_time: int = 10,
        match_similarity: float = 0.95,
    ):
        """
        等待图像出现或消失
        :param input_data: 目标图像
        :param wait_type: 等待类型
        :param wait_time: 超时时间
        :param match_similarity: 匹配相似度
        :return: 等待结果
        """
        start_time = time.time()

        if wait_type == WaitType.DISAPPEAR:
            target_rect = CvCore.match_imgs(input_data, match_similarity)
            if not target_rect:
                raise BaseException(TARGET_EXISTS_ERROR, "当前界面元素不存在，无法判断消失状态")

        while True:
            target_rect = CvCore.match_imgs(input_data, match_similarity)

            if wait_type == WaitType.APPEAR:
                if target_rect is not None:
                    return True
            elif wait_type == WaitType.DISAPPEAR:
                if target_rect is None:
                    return True
            else:
                raise NotImplementedError()

            if time.time() - start_time > wait_time:
                break

            time.sleep(0.5)

        return False

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "input_data",
                formType=AtomicFormTypeMeta(AtomicFormType.PICK.value, params={"use": "CV"}),
                noInput=True,
            ),
            atomicMg.param("input_type", required=False),
            atomicMg.param(
                "input_content",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.input_content.show",
                        expression="return $this.input_type.value == '{}'".format(InputType.TEXT.value),
                    )
                ],
            ),
            atomicMg.param(
                "simulate_flag",
                formType=AtomicFormTypeMeta(AtomicFormType.SWITCH.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.simulate_flag.show",
                        expression="return $this.input_type.value == '{}'".format(InputType.TEXT.value),
                    )
                ],
                required=False,
            ),
            atomicMg.param(
                "interval",
                types="Float",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.interval.show",
                        expression="return $this.input_type.value == '{}'".format(InputType.TEXT.value),
                    )
                ],
            ),
            atomicMg.param("wait_time", types="Int", required=False),
            atomicMg.param(
                "match_similarity",
                formType=AtomicFormTypeMeta(AtomicFormType.SLIDER.value),
                required=False,
            ),
        ],
        outputList=[],
    )
    def image_input(
        input_data: IMGPick,
        input_type: InputType = InputType.TEXT,
        input_content: str = "",
        simulate_flag: Simulate_flag = Simulate_flag.YES,
        interval: float = 0.1,
        match_similarity: float = 0.95,
        wait_time: int = 10,
    ):
        """
        图像输入框输入
        :param input_data: 目标图像
        :param input_type: 输入类型
        :param input_content: 输入内容
        :param simulate_flag: 是否模拟输入
        :param interval: 模拟输入间隔
        :param wait_time: 等待时间
        :param match_similarity: 匹配相似度
        """
        start_time = time.time()
        while True:
            target_rect = CvCore.match_imgs(input_data, match_similarity)
            if target_rect is not None:
                try:
                    Mouse.click(
                        x=target_rect[0] + target_rect[2] / 2,
                        y=target_rect[1] + target_rect[3] / 2,
                    )
                    if input_type == InputType.TEXT:
                        message = str(input_content)
                        if simulate_flag == Simulate_flag.YES:
                            # Keyboard.change_language(ENGLISH)
                            for char in message:
                                random_num = random.uniform(0, interval)
                                Keyboard.write_unicode(char)
                                time.sleep(random_num)
                            # Keyboard.change_language(CHINESE)
                        elif simulate_flag == Simulate_flag.NO:
                            # Keyboard.change_language(ENGLISH)
                            for char in message:
                                Keyboard.write_unicode(char)
                                time.sleep(interval)
                            # Keyboard.change_language(CHINESE)
                        else:
                            raise NotImplementedError()
                    elif input_type == InputType.CLIP:
                        msg = Clipboard.paste()
                        if not msg:
                            raise BaseException(CLIP_PASTE_ERROR, "Clip is empty.")
                        else:
                            Keyboard.hotkey("ctrl", "v")
                            Clipboard.clear()
                    else:
                        raise NotImplementedError()

                    return True
                except Exception as e:
                    raise BaseException(CV_INPUT_ERROR, "输入失败，请检查输入信息")
            else:
                if time.time() - start_time > wait_time:
                    break
                else:
                    time.sleep(0.5)

        raise BaseException(CV_MATCH_ERROR, "超时未匹配到目标元素，请检查当前界面或降低匹配相似度重试")

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "is_regex",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
            atomicMg.param(
                "exist_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
            atomicMg.param("wait_time", types="Int"),
        ],
    )
    def ocr_text_exist(
        text: str,
        is_regex: bool = False,
        exist_type: ExistType = ExistType.EXIST,
        x1: int = 0,
        y1: int = 0,
        x2: int = 0,
        y2: int = 0,
        wait_time: int = 10,
    ) -> bool:
        """
        判断屏幕上是否存在指定文本(OCR)
        :param text: 待查找文本
        :param is_regex: 是否正则表达式
        :param exist_type: 存在/不存在
        :param x1: 查找区域左上角X（0表示全屏）
        :param y1: 查找区域左上角Y
        :param x2: 查找区域右下角X
        :param y2: 查找区域右下角Y
        :param wait_time: 等待时间(秒)
        """
        start_time = time.time()
        while True:
            if x2 > x1 and y2 > y1:
                screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
            else:
                screenshot = pyautogui.screenshot()
            page_text = CV.__ocr_screen_text__(screenshot)

            if is_regex:
                found = re.search(str(text), page_text) is not None
            else:
                found = str(text) in page_text

            if exist_type == ExistType.EXIST and found:
                return True
            if exist_type == ExistType.NOT_EXIST and not found:
                return True

            if time.time() - start_time > wait_time:
                break
            time.sleep(0.5)

        return False

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "is_regex",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
            atomicMg.param("x1", types="Int"),
            atomicMg.param("y1", types="Int"),
            atomicMg.param("x2", types="Int"),
            atomicMg.param("y2", types="Int"),
            atomicMg.param("similar_index", types="Int", required=False),
            atomicMg.param("btn_type", required=False),
            atomicMg.param("btn_model", required=False),
            atomicMg.param("ctrl_type", level=AtomicLevel.ADVANCED.value, required=False),
            atomicMg.param("click_position", required=False),
            atomicMg.param(
                "specified_position",
                formType=AtomicFormTypeMeta(AtomicFormType.GRID.value),
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.specified_position.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "horizontal_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.horizontal_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "vertical_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.vertical_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param("move_type", level=AtomicLevel.ADVANCED.value, required=False),
            atomicMg.param(
                "move_speed",
                level=AtomicLevel.ADVANCED.value,
                dynamics=[
                    DynamicsItem(
                        key="$this.move_speed.show",
                        expression="return ['{}','{}'].includes($this.move_type.value)".format(
                            MoveType.LINEAR.value, MoveType.SIMULATION.value
                        ),
                    )
                ],
                required=False,
            ),
            atomicMg.param(
                "wait_time",
                types="Int",
                level=AtomicLevel.ADVANCED.value,
                required=False,
            ),
        ],
        outputList=[],
    )
    def ocr_click(
        text: str,
        is_regex: bool = False,
        x1: int = 0,
        y1: int = 0,
        x2: int = 0,
        y2: int = 0,
        similar_index: int = 1,
        btn_type: BtnType = BtnType.LEFT,
        btn_model: BtnModel = BtnModel.CLICK,
        ctrl_type: ControlType = ControlType.EMPTY,
        click_position: PositionType = PositionType.CENTER,
        specified_position=5,
        horizontal_move: int = 0,
        vertical_move: int = 0,
        move_type: MoveType = MoveType.LINEAR,
        move_speed: Speed = Speed.NORMAL,
        wait_time: int = 10,
    ):
        """
        点击文本(OCR)：OCR识别屏幕文本并点击匹配文本位置
        :param text: 待查找文本
        :param is_regex: 是否正则表达式
        :param x1: 查找区域左上角X（0表示全屏）
        :param y1: 查找区域左上角Y
        :param x2: 查找区域右下角X
        :param y2: 查找区域右下角Y
        :param similar_index: 相似结果位置，第几个匹配的文本（从1开始）
        :param btn_type: 鼠标按键
        :param btn_model: 点击方式（单击/双击）
        :param ctrl_type: 键盘辅助按键
        :param click_position: 点击位置
        :param specified_position: 指定位置
        :param horizontal_move: 横向平移
        :param vertical_move: 纵向平移
        :param move_type: 移动方式
        :param move_speed: 移动速度
        :param wait_time: 等待时间(秒)
        :return: 空
        """
        start_time = time.time()
        while True:
            if x2 > x1 and y2 > y1:
                screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
                offset_x, offset_y = x1, y1
            else:
                screenshot = pyautogui.screenshot()
                offset_x, offset_y = 0, 0
            rects = CV.__ocr_locate_text__(screenshot, offset_x, offset_y, text, is_regex)
            if rects and 1 <= similar_index <= len(rects):
                target_rect = rects[similar_index - 1]
                try:
                    if click_position == PositionType.CENTER:
                        target_x = target_rect[0] + target_rect[2] // 2
                        target_y = target_rect[1] + target_rect[3] // 2
                    elif click_position == PositionType.RANDOM:
                        target_x = target_rect[0] + random.randint(0, target_rect[2])
                        target_y = target_rect[1] + random.randint(0, target_rect[3])
                    elif click_position == PositionType.SPECIFIC:
                        position = specified_position
                        if position is None:
                            raise BaseException(SPECIFIC_POSITION_ERROR, "未指定点击位置，请检查参数")
                        target_x, target_y = CvCore.get_region_position(
                            target_rect, position, horizontal_move, vertical_move
                        )
                    else:
                        raise NotImplementedError()

                    screen_weight, screen_height = Mouse.screen_size()
                    if target_x < 0 or target_x > screen_weight or target_y < 0 or target_y > screen_height:
                        raise BaseException(REGION_ERROR, "坐标参数不合法！")

                    if move_type == MoveType.LINEAR:
                        Mouse.move(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.linear,
                        )
                    elif move_type == MoveType.SIMULATION:
                        Mouse.move_simulate(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.easeInOutQuad,  # type: ignore
                        )
                    elif move_type == MoveType.TELEPORTATION:
                        Mouse.move(target_x, target_y, duration=0)
                    else:
                        raise NotImplementedError()

                    if ctrl_type != ControlType.EMPTY:
                        Keyboard.key_down(ctrl_type.value)
                    try:
                        if btn_model == BtnModel.CLICK:
                            Mouse.click(None, None, 1, 0, btn_type.value)
                        elif btn_model == BtnModel.DOUBLE_CLICK:
                            Mouse.click(None, None, 2, 0, btn_type.value)
                        else:
                            raise NotImplementedError()
                    finally:
                        if ctrl_type != ControlType.EMPTY:
                            Keyboard.key_up(ctrl_type.value)

                    return True
                except BaseException:
                    raise
                except Exception:
                    raise BaseException(MOUSE_CLICK_ERROR, "鼠标点击失败")
            else:
                if time.time() - start_time > wait_time:
                    break
                time.sleep(0.5)

        raise BaseException(CV_MATCH_ERROR, "超时未匹配到目标文本，请检查当前界面或调整查找文本")

    @staticmethod
    @atomicMg.atomic(
        "CV",
        inputList=[
            atomicMg.param(
                "text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "is_regex",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
            atomicMg.param("x1", types="Int"),
            atomicMg.param("y1", types="Int"),
            atomicMg.param("x2", types="Int"),
            atomicMg.param("y2", types="Int"),
            atomicMg.param("similar_index", types="Int", required=False),
            atomicMg.param("click_position", required=False),
            atomicMg.param(
                "specified_position",
                formType=AtomicFormTypeMeta(AtomicFormType.GRID.value),
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.specified_position.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "horizontal_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.horizontal_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param(
                "vertical_move",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.vertical_move.show",
                        expression="return $this.click_position.value == '{}'".format(PositionType.SPECIFIC.value),
                    )
                ],
            ),
            atomicMg.param("move_type", level=AtomicLevel.ADVANCED.value, required=False),
            atomicMg.param(
                "move_speed",
                level=AtomicLevel.ADVANCED.value,
                dynamics=[
                    DynamicsItem(
                        key="$this.move_speed.show",
                        expression="return ['{}','{}'].includes($this.move_type.value)".format(
                            MoveType.LINEAR.value, MoveType.SIMULATION.value
                        ),
                    )
                ],
                required=False,
            ),
            atomicMg.param(
                "wait_time",
                types="Int",
                level=AtomicLevel.ADVANCED.value,
                required=False,
            ),
        ],
        outputList=[],
    )
    def ocr_hover(
        text: str,
        is_regex: bool = False,
        x1: int = 0,
        y1: int = 0,
        x2: int = 0,
        y2: int = 0,
        similar_index: int = 1,
        click_position: PositionType = PositionType.CENTER,
        specified_position=5,
        horizontal_move: int = 0,
        vertical_move: int = 0,
        move_type: MoveType = MoveType.LINEAR,
        move_speed: Speed = Speed.NORMAL,
        wait_time: int = 10,
    ):
        """
        鼠标悬停在文本上(OCR)：OCR识别屏幕文本并悬停在匹配文本位置
        :param text: 待查找文本
        :param is_regex: 是否正则表达式
        :param x1: 查找区域左上角X（0表示全屏）
        :param y1: 查找区域左上角Y
        :param x2: 查找区域右下角X
        :param y2: 查找区域右下角Y
        :param similar_index: 相似结果位置，第几个匹配的文本（从1开始）
        :param click_position: 悬停位置
        :param specified_position: 指定位置
        :param horizontal_move: 横向平移
        :param vertical_move: 纵向平移
        :param move_type: 移动方式
        :param move_speed: 移动速度
        :param wait_time: 等待时间(秒)
        :return: 空
        """
        start_time = time.time()
        while True:
            if x2 > x1 and y2 > y1:
                screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
                offset_x, offset_y = x1, y1
            else:
                screenshot = pyautogui.screenshot()
                offset_x, offset_y = 0, 0
            rects = CV.__ocr_locate_text__(screenshot, offset_x, offset_y, text, is_regex)
            if rects and 1 <= similar_index <= len(rects):
                target_rect = rects[similar_index - 1]
                try:
                    if click_position == PositionType.CENTER:
                        target_x = target_rect[0] + target_rect[2] // 2
                        target_y = target_rect[1] + target_rect[3] // 2
                    elif click_position == PositionType.RANDOM:
                        target_x = target_rect[0] + random.randint(0, target_rect[2])
                        target_y = target_rect[1] + random.randint(0, target_rect[3])
                    elif click_position == PositionType.SPECIFIC:
                        position = specified_position
                        if position is None:
                            raise BaseException(SPECIFIC_POSITION_ERROR, "未指定点击位置，请检查参数")
                        target_x, target_y = CvCore.get_region_position(
                            target_rect, position, horizontal_move, vertical_move
                        )
                    else:
                        raise NotImplementedError()

                    screen_weight, screen_height = Mouse.screen_size()
                    if target_x < 0 or target_x > screen_weight or target_y < 0 or target_y > screen_height:
                        raise BaseException(REGION_ERROR, "坐标参数不合法！")

                    if move_type == MoveType.LINEAR:
                        Mouse.move(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.linear,
                        )
                    elif move_type == MoveType.SIMULATION:
                        Mouse.move_simulate(
                            target_x,
                            target_y,
                            duration=speed_to_int[move_speed],
                            tween=pyautogui.easeInOutQuad,  # type: ignore
                        )
                    elif move_type == MoveType.TELEPORTATION:
                        Mouse.move(target_x, target_y, duration=0)
                    else:
                        raise NotImplementedError()

                    return True
                except BaseException:
                    raise
                except Exception:
                    raise BaseException(MOUSE_HOVER_ERROR, "鼠标悬停失败")
            else:
                if time.time() - start_time > wait_time:
                    break
                time.sleep(0.5)

        raise BaseException(CV_MATCH_ERROR, "超时未匹配到目标文本，请检查当前界面或调整查找文本")

    @staticmethod
    def __ocr_screen_text__(screenshot) -> str:
        """截图OCR识别全部文本"""
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        image_b64 = str(base64.b64encode(buf.getvalue()), "UTF-8")
        body = {"encoding": "png", "image": image_b64, "status": 3}
        port = atomicMg.cfg().get("GATEWAY_PORT") if atomicMg.cfg().get("GATEWAY_PORT") else "13159"
        url = "http://127.0.0.1:{}/api/rpa-ai-service/ocr/general".format(port)
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers={"content-type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                ret = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise BaseException(CV_MATCH_ERROR, "OCR服务无响应或错误: {}".format(e))
        try:
            ret_dict = json.loads(base64.b64decode(ret["payload"]["result"]["text"]).decode())
            lines = ret_dict["pages"][0]["lines"]
        except Exception:
            return ""
        contents = []
        for line in lines:
            if line.get("words"):
                for word in line["words"]:
                    contents.append(word.get("content", ""))
        return "".join(contents)

    @staticmethod
    def __ocr_locate_text__(screenshot, offset_x: int, offset_y: int, text, is_regex: bool) -> list:
        """
        截图OCR并返回匹配文本的矩形列表
        按行拼接word文本做匹配，命中行返回所有word坐标的并集矩形
        :return: [(left, top, width, height), ...] 屏幕坐标
        """
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        image_b64 = str(base64.b64encode(buf.getvalue()), "UTF-8")
        body = {"encoding": "png", "image": image_b64, "status": 3}
        port = atomicMg.cfg().get("GATEWAY_PORT") if atomicMg.cfg().get("GATEWAY_PORT") else "13159"
        url = "http://127.0.0.1:{}/api/rpa-ai-service/ocr/general".format(port)
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers={"content-type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                ret = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise BaseException(CV_MATCH_ERROR, "OCR服务无响应或错误: {}".format(e))
        try:
            ret_dict = json.loads(base64.b64decode(ret["payload"]["result"]["text"]).decode())
            lines = ret_dict["pages"][0]["lines"]
        except Exception:
            return []
        results = []
        for line in lines:
            words = line.get("words") or []
            if not words:
                continue
            line_text = "".join(word.get("content", "") for word in words)
            if is_regex:
                if not re.search(str(text), line_text):
                    continue
            else:
                if str(text) not in line_text:
                    continue
            all_coords = []
            for word in words:
                all_coords.extend(word.get("coords") or [])
            if not all_coords:
                continue
            xs = [int(p[0]) for p in all_coords]
            ys = [int(p[1]) for p in all_coords]
            left, top = min(xs), min(ys)
            results.append((left + offset_x, top + offset_y, max(xs) - left, max(ys) - top))
        return results
