import time
from typing import Union

from astronverse.actionlib.report import report as step_report
from astronverse.actionlib.types import WinPick
from astronverse.baseline.logger.logger import logger
from astronverse.locator import ILocator
from astronverse.locator.core.heal_store import format_report_tips
from astronverse.locator.locator import locator
from astronverse.winelement.core import IWinEleCore
from astronverse.winelement.error import *


class WinEleCore(IWinEleCore):
    @staticmethod
    def find(pick: WinPick, wait_time: float = 10.0) -> Union["ILocator", list["ILocator"]]:
        """
        find 查找 handle
        """
        # 防止重复获取
        if pick.locator is not None:
            return pick.locator

        res = None
        locate_report = {}
        while wait_time >= 0:
            start = time.time()
            try:
                # report 回写自愈/CV 降级信息, 定位成功后在步骤日志提示用户
                locate_report = {}
                res = locator.locator(pick.get("elementData"), report=locate_report)
                if isinstance(res, list):
                    break
                window_control = res.control()
                if window_control:
                    break
            except Exception as e:
                logger.warning("WinEleCore find error: {}".format(e))
                pass
            time.sleep(0.5)
            wait_time = wait_time - (time.time() - start)
        if wait_time < 0:
            raise BaseException(ELEMENT_NO_FOUND, "等待后未找到元素！")
        # 自愈命中/CV 降级对用户可见: 避免"元素路径变了为何还能跑成功"的困惑
        for tip in format_report_tips(locate_report):
            step_report.warning(tip)
        return res
