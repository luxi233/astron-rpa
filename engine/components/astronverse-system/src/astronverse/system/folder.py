import os
import shutil
import sys

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, AtomicLevel, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.system import *
from astronverse.system.error import *
from astronverse.system.utils import (
    folder_is_exists,
    generate_copy,
    get_file_name_only,
    linux_open_folder,
    list_to_excel,
    windows_open_folder,
)

if sys.platform == "win32":
    open_folder = windows_open_folder
else:
    open_folder = linux_open_folder


class Folder:
    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param("exist_type", required=False),
        ],
    )
    def folder_exist(folder_path: str = "", exist_type: ExistType = ExistType.EXIST) -> bool:
        """
        判断文件夹是否存在，返回判断结果folder_exist_result
        """
        if exist_type == ExistType.EXIST:
            return folder_is_exists(folder_path)
        elif exist_type == ExistType.NOT_EXIST:
            return not folder_is_exists(folder_path)
        else:
            raise NotImplementedError()

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
        ],
    )
    def folder_open(folder_path: str = ""):
        """
        打开文件夹
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "文件夹不存在，请检查路径信息！",
            )

        open_folder(folder_path)

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "target_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "folder_name",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON.value,
                    params={"size": "middle"},
                ),
            ),
            atomicMg.param(
                "exist_options",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param(
                "new_folder_path",
                types="Str",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RESULT.value),
            ),
        ],
    )
    def folder_create(
        target_path: str = "",
        folder_name: str = "",
        exist_options: OptionType = OptionType.GENERATE,
    ) -> str:
        """
        新建文件夹，返回新建的文件夹路径
        """
        if not folder_is_exists(target_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(target_path),
                "填写的目录路径不存在，请检查目标路径！",
            )
        folder_path = os.path.join(target_path, folder_name)
        if folder_is_exists(folder_path):
            if exist_options == OptionType.OVERWRITE:
                shutil.rmtree(folder_path)
            elif exist_options == OptionType.SKIP:
                return folder_path
            elif exist_options == OptionType.GENERATE:
                folder_path = generate_copy(target_path, folder_name)
            else:
                raise NotImplementedError()
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param("delete_options", required=False),
        ],
        outputList=[atomicMg.param("delete_folder_result", types="Bool")],
    )
    def folder_delete(folder_path: str = "", delete_options: DeleteType = DeleteType.DELETE):
        """
        删除指定文件夹，删除操作可选  彻底删除/移入回收站
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "指定文件夹不存在，请检查文件夹路径！",
            )
        if delete_options == DeleteType.DELETE:
            shutil.rmtree(folder_path)
        elif delete_options == DeleteType.TRASH:
            from send2trash import send2trash

            send2trash(folder_path)
        else:
            raise NotImplementedError()

        return True

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "source_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "target_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "folder_name",
                formType=AtomicFormTypeMeta(type=AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param(
                "exist_options",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param(
                "copy_folder_path",
                types="Str",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RESULT.value),
            ),
        ],
    )
    def folder_copy(
        source_path: str = "",
        target_path: str = "",
        state_type: StateType = StateType.ERROR,
        folder_name: str = "",
        exist_options: OptionType = OptionType.GENERATE,
    ) -> str:
        """
        复制文件夹
        """
        if not folder_is_exists(source_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(source_path),
                "复制文件夹不存在，请检查文件夹路径！",
            )
        if not folder_is_exists(target_path):
            if state_type == StateType.CREATE:
                os.makedirs(target_path, exist_ok=True)
            elif state_type == StateType.ERROR:
                raise BaseException(
                    FOLDER_PATH_ERROR_FORMAT.format(target_path),
                    "文件夹不存在，请检查文件夹路径",
                )
            else:
                raise NotImplementedError()
        if not folder_name:
            path = source_path.rstrip("/\\")
            folder_name = os.path.basename(path)

        copy_folder_path = os.path.join(target_path, folder_name)
        if folder_is_exists(copy_folder_path):
            if exist_options == OptionType.OVERWRITE:
                shutil.rmtree(copy_folder_path)
            elif exist_options == OptionType.SKIP:
                return copy_folder_path
            elif exist_options == OptionType.GENERATE:
                copy_folder_path = generate_copy(target_path, folder_name)
            else:
                raise NotImplementedError()
        shutil.copytree(source_path, copy_folder_path)
        return copy_folder_path

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "target_folder",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "folder_name",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param(
                "exist_options",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("move_folder_path", types="Str"),
        ],
    )
    def folder_move(
        folder_path: str = "",
        target_folder: str = "",
        state_type: StateType = StateType.ERROR,
        folder_name: str = "",
        exist_options: OptionType = OptionType.GENERATE,
    ) -> str:
        """
        移动文件夹到目标文件夹中。
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "指定文件夹不存在，请检查路径信息",
            )
        if not folder_is_exists(target_folder):
            if state_type == StateType.CREATE:
                os.makedirs(target_folder, exist_ok=True)
            elif state_type == StateType.ERROR:
                raise BaseException(
                    FOLDER_PATH_ERROR_FORMAT.format(target_folder),
                    "文件夹不存在，请检查文件夹路径",
                )
            else:
                raise NotImplementedError()

        if not folder_name:
            path = folder_path.rstrip("/\\")
            folder_name = os.path.basename(path)
        target_path = os.path.join(target_folder, folder_name)

        if folder_is_exists(target_path):
            if exist_options == OptionType.OVERWRITE:
                shutil.rmtree(target_path)
            elif exist_options == OptionType.SKIP:
                return target_path
            elif exist_options == OptionType.GENERATE:
                target_path = generate_copy(target_folder, folder_name)
            else:
                raise NotImplementedError()

        folder_move_path = shutil.move(folder_path, target_path)
        return folder_move_path

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "new_name",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
            ),
            atomicMg.param(
                "exist_options",
                formType=AtomicFormTypeMeta(type=AtomicFormType.SELECT.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("rename_folder_path", types="Str"),
        ],
    )
    def folder_rename(
        folder_path: str = "",
        new_name: str = "",
        exist_options: OptionType = OptionType.GENERATE,
    ) -> str:
        """
        重命名文件夹
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "文件夹不存在，请检查路径信息",
            )

        path = folder_path.rstrip("/\\")
        if new_name == os.path.basename(path):
            raise BaseException(
                RENAME_ERROR_FORMAT.format(new_name),
                "重命名名称与原名称一致，请检查输入内容",
            )
        folder_dir = os.path.dirname(folder_path)
        rename_folder_path = os.path.join(folder_dir, new_name)

        if folder_is_exists(rename_folder_path):
            if exist_options == OptionType.SKIP:
                return rename_folder_path
            elif exist_options == OptionType.GENERATE:
                rename_folder_path = generate_copy(folder_dir, new_name)
            elif exist_options == OptionType.OVERWRITE:
                shutil.rmtree(rename_folder_path)
            else:
                raise NotImplementedError()

        os.rename(folder_path, rename_folder_path)
        return rename_folder_path

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("clear_folder_result", types="Bool"),
        ],
    )
    def folder_clear(folder_path: str = ""):
        """
        清空指定文件夹
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "文件夹不存在，请检查路径信息",
            )

        from send2trash import send2trash

        for root, dirs, files in os.walk(folder_path, topdown=False):
            for name in files:
                try:
                    send2trash(os.path.join(root, name))
                except Exception as e:
                    raise BaseException(
                        FILE_DELETE_ERROR_FORMAT.format(os.path.join(root, name)),
                        "文件删除失败，请检查文件是否正在被其他程序使用",
                    )
            for name in dirs:
                try:
                    send2trash(os.path.join(root, name))
                except Exception as e:
                    raise BaseException(
                        FOLDER_DELETE_ERROR_FORMAT.format(os.path.join(root, name)),
                        "文件夹删除失败",
                    )
        return True

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "excel_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
                dynamics=[
                    DynamicsItem(
                        key="$this.excel_path.show",
                        expression="return $this.output_type.value == '{}'".format(OutputType.EXCEL.value),
                    )
                ],
                required=True,
            ),
            atomicMg.param(
                "state_type",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.state_type.show",
                        expression="return $this.output_type.value == '{}'".format(OutputType.EXCEL.value),
                    )
                ],
            ),
            atomicMg.param(
                "excel_name",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.excel_name.show",
                        expression="return $this.output_type.value == '{}'".format(OutputType.EXCEL.value),
                    )
                ],
            ),
            atomicMg.param("output_type", required=False),
            atomicMg.param("traverse_subfolder", required=False),
            atomicMg.param("sort_method", level=AtomicLevel.ADVANCED.value),
            atomicMg.param(
                "sort_type",
                dynamics=[
                    DynamicsItem(
                        key="$this.sort_type.show",
                        expression="return $this.sort_method.value ['{}', '{}']".format(
                            SortMethod.CTIME.value, SortMethod.MTIME.value
                        ),
                    )
                ],
                level=AtomicLevel.ADVANCED.value,
            ),
        ],
        outputList=[
            atomicMg.param("folder_list", types="List"),
        ],
    )
    def get_folder_list(
        folder_path: str = "",
        traverse_subfolder: TraverseType = TraverseType.NO,
        output_type: OutputType = OutputType.LIST,
        excel_path: str = "",
        state_type: StateType = StateType.ERROR,
        excel_name: str = "",
        sort_method: SortMethod = SortMethod.NONE,
        sort_type: SortType = SortType.ASCENDING,
    ) -> list:
        """
        获取文件夹列表
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "文件夹不存在，请检查路径信息",
            )

        # 获取文件夹列表(去除隐藏文件）
        folder_list = []
        if traverse_subfolder == TraverseType.YES:
            for root, dirs, _ in os.walk(folder_path):
                folder_list.extend(os.path.join(root, folder) for folder in dirs if not folder.startswith("."))
        elif traverse_subfolder == TraverseType.NO:
            folder_list = [
                os.path.join(folder_path, folder)
                for folder in os.listdir(folder_path)
                if folder_is_exists(os.path.join(folder_path, folder)) and not folder.startswith(".")
            ]
        else:
            raise NotImplementedError()

        # 排序
        if sort_method == SortMethod.NONE:
            pass
        elif sort_method == SortMethod.CTIME:
            folder_list = sorted(folder_list, key=lambda x: os.path.getctime(x))
            folder_list = folder_list[::-1] if sort_type == SortType.DESCENDING else folder_list
        elif sort_method == SortMethod.MTIME:
            folder_list = sorted(folder_list, key=lambda x: os.path.getmtime(x))
            folder_list = folder_list[::-1] if sort_type == SortType.DESCENDING else folder_list
        else:
            raise NotImplementedError()

        # 输出
        if output_type == OutputType.EXCEL:
            if not folder_is_exists(excel_path):
                if state_type == StateType.ERROR:
                    raise BaseException(
                        FILE_PATH_ERROR_FORMAT.format(excel_path),
                        "指定excel存储路径不存在，请检查路径信息",
                    )
                elif state_type == StateType.CREATE:
                    os.makedirs(excel_path, exist_ok=True)
                else:
                    raise NotImplementedError()

            if not os.path.splitext(excel_name)[1] == ".xlsx":
                if os.path.splitext(excel_name)[1]:
                    excel_name = get_file_name_only(excel_name)
                excel_name += ".xlsx"

            excel_path = os.path.join(excel_path, excel_name)
            list_to_excel(path_list=folder_list, excel_path=excel_path)
            return folder_list
        elif output_type == OutputType.LIST:
            return folder_list
        else:
            raise NotImplementedError()

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param("system_folder_type"),
        ],
        outputList=[atomicMg.param("system_folder_path", types="Str")],
    )
    def get_system_folder(system_folder_type: SystemFolderType = SystemFolderType.DESKTOP) -> str:
        """
        获取系统文件夹路径（桌面/文档/下载/图片/音乐/视频/收藏夹/开始菜单/临时目录）
        :param system_folder_type: 系统文件夹类型
        :return: 系统文件夹绝对路径
        """
        import platform

        system = platform.system()
        folder_key = system_folder_type.value

        if system == "Windows":
            path = _get_windows_known_folder(folder_key)
        elif system == "Darwin":
            path = _get_mac_known_folder(folder_key)
        else:
            path = _get_linux_known_folder(folder_key)

        if path is None:
            raise BaseException(
                SYSTEM_FOLDER_NOT_SUPPORTED_FORMAT.format(folder_key),
                f"当前操作系统({system})不支持获取该系统文件夹，请检查文件夹类型",
            )
        if not folder_is_exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                raise BaseException(SYSTEM_FOLDER_GET_ERROR_FORMAT.format(folder_key, str(e)), str(e))
        return path

    @staticmethod
    @atomicMg.atomic(
        "Folder",
        inputList=[
            atomicMg.param(
                "folder_path",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "folder"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("is_empty", types="Bool"),
        ],
    )
    def is_empty_folder(folder_path: str = "") -> bool:
        """
        判断文件夹是否为空
        :param folder_path: 文件夹路径
        :return: 文件夹是否为空(不存在也视为空)
        """
        if not folder_is_exists(folder_path):
            raise BaseException(
                FOLDER_PATH_ERROR_FORMAT.format(folder_path),
                "文件夹不存在，请检查路径信息",
            )
        return len(os.listdir(folder_path)) == 0


def _get_windows_known_folder(folder_key: str):
    """通过SHGetKnownFolderPath获取Windows已知文件夹路径，失败返回None"""
    import ctypes
    from ctypes import wintypes

    if folder_key == "temp":
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.kernel32.GetTempPathW(260, buf):
            return buf.value.rstrip("\\/")
        return None

    known_guids = {
        "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
        "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
        "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
        "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
        "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
        "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
        "favorites": "{1777F761-68AD-4D8A-87BD-30B7590E2341}",
        "start_menu": "{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}",
    }
    guid_str = known_guids.get(folder_key)
    if not guid_str:
        return None

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    guid = _GUID()
    ctypes.windll.ole32.CLSIDFromString(guid_str, ctypes.byref(guid))
    ppath = ctypes.c_wchar_p()
    try:
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ppath))
        if hr != 0:
            return None
        return ppath.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ppath)


def _get_mac_known_folder(folder_key: str):
    """macOS已知文件夹路径，不支持返回None"""
    import tempfile

    home = os.path.expanduser("~")
    mapping = {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Movies"),
        "favorites": os.path.join(home, "Library", "Favorites"),
        "temp": tempfile.gettempdir(),
    }
    return mapping.get(folder_key)


def _get_linux_known_folder(folder_key: str):
    """Linux XDG用户目录，不支持返回None"""
    import tempfile

    if folder_key == "temp":
        return tempfile.gettempdir()

    home = os.path.expanduser("~")
    xdg_names = {
        "desktop": "XDG_DESKTOP_DIR",
        "documents": "XDG_DOCUMENTS_DIR",
        "downloads": "XDG_DOWNLOAD_DIR",
        "pictures": "XDG_PICTURES_DIR",
        "music": "XDG_MUSIC_DIR",
        "videos": "XDG_VIDEOS_DIR",
    }
    xdg_name = xdg_names.get(folder_key)
    if not xdg_name:
        return None

    user_dirs_file = os.path.join(home, ".config", "user-dirs.dirs")
    if os.path.exists(user_dirs_file):
        import re

        with open(user_dirs_file, encoding="utf-8") as f:
            for line in f:
                match = re.match(rf'{xdg_name}="\$HOME/(.+)"', line.strip())
                if match:
                    return os.path.join(home, match.group(1))

    fallback = {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
    }
    return fallback.get(folder_key)
