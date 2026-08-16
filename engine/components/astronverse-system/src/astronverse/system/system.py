import os
import platform
import random
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.system import *
from astronverse.system.core.printer_core import PrinterCore
from astronverse.system.core.screenshot_core import ScreenShotCore
from astronverse.system.core.selection_core import get_selected_files
from astronverse.system.core import app_core, ime_core, screensaver_core
from astronverse.system.error import *
from astronverse.system.utils import file_is_exists, folder_is_exists, get_files_in_folder, path_join

ScreenShotCore = ScreenShotCore()


class System:
    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param("wait_type"),
            atomicMg.param(
                "delay",
                types="Float",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.delay.show",
                        expression="return $this.wait_type.value == '{}'".format(WaitType.FIXED.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "min_delay",
                types="Float",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.min_delay.show",
                        expression="return $this.wait_type.value == '{}'".format(WaitType.RANDOM.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "max_delay",
                types="Float",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.max_delay.show",
                        expression="return $this.wait_type.value == '{}'".format(WaitType.RANDOM.value),
                    )
                ],
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("wait_seconds", types="Float"),
        ],
    )
    def wait(
        wait_type: WaitType = WaitType.FIXED,
        delay: float = 1,
        min_delay: float = 1,
        max_delay: float = 5,
    ):
        """
        等待指定时长后继续执行流程
        """
        if wait_type == WaitType.RANDOM:
            min_value = float(min_delay)
            max_value = float(max_delay)
            if min_value < 0 or max_value < 0:
                raise ValueError("随机等待时长不能为负数，请检查最小时长与最大时长设置")
            if min_value > max_value:
                raise ValueError("最小时长{}秒不能大于最大时长{}秒".format(min_value, max_value))
            wait_seconds = round(random.uniform(min_value, max_value), 3)
        else:
            wait_seconds = float(delay)
            if wait_seconds < 0:
                raise ValueError("等待时长不能为负数，请检查时长设置")

        time.sleep(wait_seconds)
        return wait_seconds

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "enable_move",
                formType=AtomicFormTypeMeta(AtomicFormType.SWITCH.value),
            ),
            atomicMg.param(
                "enable_click",
                formType=AtomicFormTypeMeta(AtomicFormType.SWITCH.value),
            ),
            atomicMg.param(
                "enable_pause",
                formType=AtomicFormTypeMeta(AtomicFormType.SWITCH.value),
            ),
            atomicMg.param(
                "min_pause",
                types="Float",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.min_pause.show",
                        expression="return $this.enable_pause.value == true",
                    ),
                ],
            ),
            atomicMg.param(
                "max_pause",
                types="Float",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.max_pause.show",
                        expression="return $this.enable_pause.value == true",
                    ),
                ],
            ),
        ],
    )
    def human_sim_start(
        enable_move: bool = True,
        enable_click: bool = True,
        enable_pause: bool = True,
        min_pause: float = 0.1,
        max_pause: float = 0.5,
    ):
        """
        开启模拟真人操作：区间内（直至执行【结束模拟真人操作】）的桌面鼠标/键盘操作
        按仿真模式执行，可降低被反爬检测的概率
        """
        from astronverse.actionlib.humansim import human_sim

        human_sim.start(
            enable_move=enable_move,
            enable_click=enable_click,
            enable_pause=enable_pause,
            min_pause=min_pause,
            max_pause=max_pause,
        )

    @staticmethod
    @atomicMg.atomic("System", inputList=[])
    def human_sim_end():
        """
        结束模拟真人操作
        """
        from astronverse.actionlib.humansim import human_sim

        human_sim.stop()

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "png_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
                required=True,
            ),
            atomicMg.param("state_type", required=False),
            atomicMg.param("png_name", types="Str", required=True),
            atomicMg.param(
                "top_left_x",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.top_left_x.show",
                        expression="return $this.screen_type.value == '{}'".format(ScreenType.REGION.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "top_left_y",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.top_left_y.show",
                        expression="return $this.screen_type.value == '{}'".format(ScreenType.REGION.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "bottom_right_x",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.bottom_right_x.show",
                        expression="return $this.screen_type.value == '{}'".format(ScreenType.REGION.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "bottom_right_y",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                dynamics=[
                    DynamicsItem(
                        key="$this.bottom_right_y.show",
                        expression="return $this.screen_type.value == '{}'".format(ScreenType.REGION.value),
                    )
                ],
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("screenshot_path", types="Str"),
        ],
    )
    def screen_shot(
        png_path: str = "",
        state_type: StateType = StateType.ERROR,
        png_name: str = "",
        screen_type: ScreenType = ScreenType.FULL,
        top_left_x: int = 0,
        top_left_y: int = 0,
        bottom_right_x: int = 0,
        bottom_right_y: int = 0,
    ):
        """
        屏幕截图
        """
        if not folder_is_exists(png_path):
            if state_type == StateType.ERROR:
                raise BaseException(
                    FOLDER_PATH_ERROR_FORMAT.format(png_path),
                    "指定保存路径不存在，请检查路径信息",
                )
            elif state_type == StateType.CREATE:
                os.makedirs(png_path, exist_ok=True)
            else:
                raise NotImplementedError()

        if not (os.path.splitext(png_name)[1] == ".png" or os.path.splitext(png_name)[1] == ".jpg"):
            png_name = png_name + ".png"
        screenshot_path = os.path.join(png_path, png_name)
        screen_width, screen_height = ScreenShotCore.screen_size()
        if screen_type == ScreenType.FULL:
            region = (0, 0, screen_width, screen_height)
            try:
                ScreenShotCore.screenshot(region=region, file_path=screenshot_path)
            except Exception as e:
                raise BaseException(SCREENSHOT_ERROR_FORMAT.format(e), "{e}")
        elif screen_type == ScreenType.REGION:
            if (
                top_left_x < 0
                or top_left_y < 0
                or bottom_right_x < 0
                or bottom_right_y < 0
                or top_left_x > screen_width
                or top_left_y > screen_height
                or bottom_right_x > screen_width
                or bottom_right_y > screen_height
            ):
                raise ValueError(
                    "输入坐标{}，{}，{}，{}须大于0且在屏幕范围[{}*{}]内".format(
                        top_left_x,
                        top_left_y,
                        bottom_right_x,
                        bottom_right_y,
                        screen_width,
                        screen_height,
                    )
                )
            region = (
                top_left_x,
                top_left_y,
                bottom_right_x - top_left_x,
                bottom_right_y - top_left_y,
            )
            try:
                ScreenShotCore.screenshot(region=region, file_path=screenshot_path)
            except Exception as e:
                raise BaseException(SCREENSHOT_ERROR_FORMAT.format(e), "{e}")
        return screenshot_path

    @staticmethod
    @atomicMg.atomic(
        "System",
        outputList=[
            atomicMg.param("screen_lock_result", types="Bool"),
        ],
    )
    def screen_lock():
        raise NotImplementedError()

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param("user_name", required=False),
            atomicMg.param("pwd_type", required=False),
            atomicMg.param(
                "password_text",
                dynamics=[
                    DynamicsItem(
                        key="$this.password_text.show",
                        expression="return $this.pwd_type.value == '{}'".format(PwdType.PASSWORD.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "password_rsa",
                dynamics=[
                    DynamicsItem(
                        key="$this.password_rsa.show",
                        expression="return $this.pwd_type.value == '{}'".format(PwdType.RSA.value),
                    )
                ],
                required=True,
            ),
        ],
        outputList=[atomicMg.param("screen_unlock_result", types="Bool")],
    )
    def screen_unlock(
        user_name: str = "",
        pwd_type: PwdType = PwdType.PASSWORD,
        password_text: str = "",
        password_rsa: str = "",
    ):
        raise NotImplementedError()

    @staticmethod
    @atomicMg.atomic(
        "System",
        outputList=[
            atomicMg.param("selected_file_list", types="List"),
        ],
    )
    def get_selected_files() -> list:
        """
        获取资源管理器/桌面(Finder)中当前选中的文件(夹)路径列表
        :return: 选中项绝对路径列表
        """
        system = platform.system()
        if system == "Linux":
            raise BaseException(SELECTED_FILES_ERROR_FORMAT.format("linux"), "当前操作系统不支持获取选中文件列表")
        try:
            selected = get_selected_files()
        except NotImplementedError:
            raise BaseException(SELECTED_FILES_ERROR_FORMAT.format(system), "当前操作系统不支持获取选中文件列表")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SELECTED_FILES_ERROR_FORMAT.format(str(e)), str(e))
        if not selected:
            raise BaseException(
                SELECTED_FILES_NOT_FOUND_FORMAT, "未找到选中的文件(夹)，请先在资源管理器或桌面中选择后再执行"
            )
        return selected

    @staticmethod
    @atomicMg.atomic(
        "System",
        outputList=[
            atomicMg.param("ime_status", types="String"),
        ],
    )
    def get_ime() -> str:
        """
        获取当前激活窗口输入法的中英文输入状态
        :return: unknow(未知)/english(英文输入状态)/chinese(中文输入状态)
        """
        if platform.system() != "Windows":
            raise BaseException(IME_NOT_SUPPORTED_FORMAT, "仅支持Windows系统")
        try:
            return ime_core.get_ime_status()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IME_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param("ime_type"),
        ],
    )
    def set_ime(ime_type: IMEStatusType = IMEStatusType.ENGLISH) -> None:
        """
        设置当前激活窗口的输入法为中/英文输入状态(仅支持Windows，支持搜狗/百度/QQ/Bing等主流输入法)
        :param ime_type: english(英文输入法)/chinese(中文输入法)
        """
        if platform.system() != "Windows":
            raise BaseException(IME_NOT_SUPPORTED_FORMAT, "仅支持Windows系统")
        try:
            ime_core.set_ime_status(ime_type.value)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IME_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic("System")
    def screensaver_start() -> None:
        """
        唤起屏幕保护(全屏置顶黑窗，如已设置屏保提示则显示提示文字)
        """
        try:
            screensaver_core.start_screensaver()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREENSAVER_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic("System")
    def screensaver_stop() -> None:
        """
        关闭已唤起的屏幕保护
        """
        try:
            stopped = screensaver_core.stop_screensaver()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREENSAVER_ERROR_FORMAT.format(str(e)), str(e))
        if not stopped:
            raise BaseException(SCREENSAVER_NOT_RUNNING_FORMAT, "当前没有已唤起的屏幕保护")

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "tip_text",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
    )
    def set_screensaver_tip(tip_text: str = "") -> None:
        """
        设置屏保提示文字(唤起屏幕保护时全屏显示，屏保运行中设置会自动刷新)
        :param tip_text: 提示文字
        """
        try:
            screensaver_core.write_tip(tip_text)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREENSAVER_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic("System")
    def clear_screensaver_tip() -> None:
        """
        清空屏保提示文字
        """
        try:
            if not screensaver_core.clear_tip():
                raise BaseException(SCREENSAVER_TIP_EMPTY_FORMAT, "当前未设置屏保提示文字")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SCREENSAVER_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "data_key",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "content",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
    )
    def save_custom_data(data_key: str = "", content: str = "") -> None:
        """
        保存自定义数据(同Key覆盖，持久保存跨流程执行可用，单条最大20000字符)
        :param key: 数据Key
        :param content: 数据内容
        """
        try:
            app_core.save_custom_data(data_key, content)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(CUSTOM_DATA_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "data_key",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("content", types="String"),
        ],
    )
    def read_custom_data(data_key: str = ""):
        """
        读取已保存的自定义数据，未保存过返回None
        :param key: 数据Key
        :return: 数据内容(未保存过返回None)
        """
        try:
            return app_core.read_custom_data(data_key)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(CUSTOM_DATA_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic("System")
    def terminate_app() -> None:
        """
        终止应用(停止整个应用的运行，后续所有流程不再执行，应用以取消状态结束)
        """
        from astronverse.actionlib.error import TerminateAppSignal

        raise TerminateAppSignal("terminate app")

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param("param_type"),
        ],
        outputList=[
            atomicMg.param("param_value", types="String"),
        ],
    )
    def get_app_param(param_type: AppParamType = AppParamType.PROJECT_ID) -> str:
        """
        获取当前应用的运行参数(应用ID/应用名称/执行ID/资源文件目录)
        :param param_type: 参数类型
        :return: 参数值
        """
        try:
            if param_type == AppParamType.PROJECT_ID:
                value = app_core.get_project_id()
            elif param_type == AppParamType.PROJECT_NAME:
                value = app_core.get_project_name()
            elif param_type == AppParamType.EXEC_ID:
                value = app_core.get_exec_id()
            else:
                value = app_core.get_resource_dir()
            return str(value)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(APP_PARAM_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "file_name",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("read_type"),
            atomicMg.param(
                "encode",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("content", types="String"),
        ],
    )
    def read_resource_file(
        file_name: str = "", read_type: ResourceReadType = ResourceReadType.TEXT, encode: str = "utf-8"
    ):
        """
        读取资源文件内容(文本或二进制)
        :param file_name: 资源文件名(相对资源目录)
        :param read_type: 读取类型: text(文本)/byte(二进制)
        :param encode: 文本编码(utf-8/gbk等)
        :return: 文件内容(文本为字符串, 二进制为bytes)
        """
        try:
            import os

            path = app_core.resolve_resource_path(file_name)
            if read_type == ResourceReadType.TEXT:
                with open(path, encoding=encode) as f:
                    return f.read()
            with open(path, "rb") as f:
                return f.read()
        except BaseException:
            raise
        except Exception as e:
            msg = str(e)
            if isinstance(e, FileNotFoundError):
                raise BaseException(RESOURCE_FILE_NOT_FOUND_FORMAT.format(file_name), msg)
            raise BaseException(RESOURCE_FILE_ERROR_FORMAT.format(msg), msg)

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "file_name",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("file_path", types="String"),
        ],
    )
    def get_resource_file_path(file_name: str = "") -> str:
        """
        获取资源文件的绝对路径
        :param file_name: 资源文件名(相对资源目录)
        :return: 文件绝对路径
        """
        try:
            return app_core.resolve_resource_path(file_name)
        except BaseException:
            raise
        except Exception as e:
            msg = str(e)
            if isinstance(e, FileNotFoundError):
                raise BaseException(RESOURCE_FILE_NOT_FOUND_FORMAT.format(file_name), msg)
            raise BaseException(RESOURCE_FILE_ERROR_FORMAT.format(msg), msg)

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "file_name",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "target_path",
                types="String",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
                required=True,
            ),
            atomicMg.param("exist_option"),
        ],
    )
    def copy_resource_file(
        file_name: str = "",
        target_path: str = "",
        exist_option: ResourceCopyExistOption = ResourceCopyExistOption.OVERWRITE,
    ) -> None:
        """
        拷贝资源文件到指定位置
        :param file_name: 资源文件名(相对资源目录)
        :param target_path: 目标文件路径
        :param exist_option: 目标文件已存在时: overwrite(覆盖)/skip(不拷贝)
        """
        try:
            import os
            import shutil

            path = app_core.resolve_resource_path(file_name)
            if os.path.exists(target_path) and exist_option == ResourceCopyExistOption.SKIP:
                return
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            shutil.copyfile(path, target_path)
        except BaseException:
            raise
        except Exception as e:
            msg = str(e)
            if isinstance(e, FileNotFoundError):
                raise BaseException(RESOURCE_FILE_NOT_FOUND_FORMAT.format(file_name), msg)
            raise BaseException(RESOURCE_FILE_ERROR_FORMAT.format(msg), msg)

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "file_name",
                types="String",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
    )
    def clipboard_resource_file(file_name: str = "") -> None:
        """
        将资源文件添加到剪切板(配合Ctrl+V可将文件粘贴到目标位置)
        :param file_name: 资源文件名(相对资源目录)
        """
        try:
            from astronverse.system.clipboard import Clipboard, ContentType

            path = app_core.resolve_resource_path(file_name)
            Clipboard.copy_clip(content_type=ContentType.FILE, file_path=path)
        except BaseException:
            raise
        except Exception as e:
            msg = str(e)
            if isinstance(e, FileNotFoundError):
                raise BaseException(RESOURCE_FILE_NOT_FOUND_FORMAT.format(file_name), msg)
            raise BaseException(RESOURCE_FILE_ERROR_FORMAT.format(msg), msg)

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param(
                "folder_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
                required=True,
            ),
            atomicMg.param(
                "file_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[
            atomicMg.param("file_path", types="Str"),
        ],
    )
    def export_log(folder_path: str = "", file_name: str = "") -> str:
        """
        导出运行日志(将当前应用的运行日志导出到txt文件)
        :param folder_path: 导出文件夹路径
        :param file_name: 导出文件名称(.txt)
        :return: 导出文件的完整路径
        """
        try:
            import os

            log_file = app_core.get_run_log_file()
            if not log_file:
                raise BaseException(LOG_EXPORT_ERROR_FORMAT, "未找到当前执行的运行日志文件")
            if file_name and not file_name.lower().endswith(".txt"):
                file_name = "{}.txt".format(file_name)
            if not file_name:
                file_name = "run_log.txt"
            os.makedirs(folder_path, exist_ok=True)
            target = os.path.join(folder_path, file_name)
            content = app_core.format_run_log(log_file)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return target
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(LOG_EXPORT_ERROR_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "System",
        inputList=[
            atomicMg.param("file_type"),
            atomicMg.param(
                "doc_app_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.doc_app_type.show",
                        expression=f"return $this.file_type.value == '{FileType.WORD.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "xls_app_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.xls_app_type.show",
                        expression=f"return $this.file_type.value == '{FileType.EXCEL.value}'",
                    )
                ],
            ),
            atomicMg.param("batch_print"),
            atomicMg.param(
                "file_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
                dynamics=[
                    DynamicsItem(
                        key="$this.file_path.show",
                        expression=f"return $this.batch_print.value == '{BatchType.SINGLE.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
                dynamics=[
                    DynamicsItem(
                        key="$this.folder_path.show",
                        expression=f"return $this.batch_print.value == '{BatchType.BATCH.value}'",
                    )
                ],
            ),
            atomicMg.param("printer_type"),  # 打印设置  系统设置和自定义设置
            atomicMg.param("printer_name", required=False),
            atomicMg.param(
                "paper_size",
                dynamics=[
                    DynamicsItem(
                        key="$this.paper_size.show",
                        expression=f"return $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "page_weight",
                types="Float",
                dynamics=[
                    DynamicsItem(
                        key="$this.page_weight.show",
                        expression=f"return $this.paper_size.value == '{PaperType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "page_height",
                types="Float",
                dynamics=[
                    DynamicsItem(
                        key="$this.page_height.show",
                        expression=f"return $this.paper_size.value == '{PaperType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "print_num",
                dynamics=[
                    DynamicsItem(
                        key="$this.print_num.show",
                        expression=f"return $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "page",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.page.show",
                        expression=f"return ($this.file_type.value == '{FileType.WORD.value}' || $this.file_type.value == '{FileType.EXCEL.value}') && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
                required=False,
            ),
            atomicMg.param(
                "orientation_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.orientation_type.show",
                        expression=f"return $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "scale",
                dynamics=[
                    DynamicsItem(
                        key="$this.scale.show",
                        expression=f"return $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "margin_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.margin_type.show",
                        expression=f"return $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "left_margin",
                dynamics=[
                    DynamicsItem(
                        key="$this.left_margin.show",
                        expression=f"return $this.margin_type.value == '{MarginType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "right_margin",
                dynamics=[
                    DynamicsItem(
                        key="$this.right_margin.show",
                        expression=f"return $this.margin_type.value == '{MarginType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "top_margin",
                dynamics=[
                    DynamicsItem(
                        key="$this.top_margin.show",
                        expression=f"return $this.margin_type.value == '{MarginType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "bottom_margin",
                dynamics=[
                    DynamicsItem(
                        key="$this.bottom_margin.show",
                        expression=f"return $this.margin_type.value == '{MarginType.CUSTOM.value}' && $this.printer_type.value == '{PrinterType.CUSTOM.value}'",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("printer_status", types="List"),
        ],
    )
    def printer(
        file_type: FileType = FileType.PDF,
        doc_app_type: DocAppType = DocAppType.DEFAULT,
        xls_app_type: XlsAppType = XlsAppType.DEFAULT,
        batch_print: BatchType = BatchType.SINGLE,
        file_path: str = "",
        folder_path: str = "",
        printer_type: PrinterType = PrinterType.DEFAULT,  # 打印设置  系统设置和自定义设置
        printer_name: str = "",
        paper_size: PaperType = PaperType.A4,
        page_weight: str = "",
        page_height: str = "",
        print_num: int = 1,
        page: str = "",
        orientation_type: OrientationType = OrientationType.VERTICAL,
        scale: int = 100,
        margin_type: MarginType = MarginType.DEFAULT,
        left_margin: float = 10,
        top_margin: float = 9.5,
        right_margin: float = 10,
        bottom_margin: float = 9.5,
    ):
        """打印机打印"""
        if batch_print == BatchType.SINGLE:
            if not file_is_exists(file_path):
                raise BaseException(
                    FILE_PATH_ERROR_FORMAT.format(file_path), "文件不存在或路径信息有误，请检查路径信息"
                )
            print_file = file_path
        elif batch_print == BatchType.BATCH:
            if not folder_is_exists(folder_path):
                raise BaseException(
                    FOLDER_PATH_ERROR_FORMAT.format(folder_path), "文件夹不存在或路径信息有误，请检查路径信息"
                )
            print_file = []
            files = get_files_in_folder(folder_path, general=True)
            for file in files:
                file_path = path_join(folder_path, file)
                print_file.append(file_path)
        else:
            raise NotImplementedError()

        if file_type == FileType.WORD:
            printer_app = str(doc_app_type.value)
        elif file_type == FileType.EXCEL:
            printer_app = str(xls_app_type.value)
        else:
            printer_app = ""

        try:
            prc = PrinterCore()
            printer_status = prc.run(
                printer_name=printer_name,
                print_file=print_file,
                batch_print=str(batch_print.value),
                file_type=str(file_type.value),
                printer_type=str(printer_type.value),
                paper_size=str(paper_size.value),
                print_num=print_num,
                scale=scale,
                margin_type=str(margin_type.value),
                margin=[left_margin, top_margin, right_margin, bottom_margin],
                orientation_type=str(orientation_type.value),
                page_weight=page_weight,
                page_height=page_height,
                pages=page,
                printer_app=printer_app,
            )
        except Exception as e:
            raise e

        return printer_status
