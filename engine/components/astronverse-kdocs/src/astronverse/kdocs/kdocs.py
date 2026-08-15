from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.kdocs import TargetType
from astronverse.kdocs.core_kdocs import WpsHookClient, WpsHookError


class Kdocs:
    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("hook_url", types="Str", required=True),
            atomicMg.param("token", types="Password", required=True),
            atomicMg.param("time_out", types="Int", required=False),
        ],
        outputList=[
            atomicMg.param("wps_client", types="Any"),
        ],
    )
    def create_client(hook_url: str, token: str, time_out: int = 30):
        """创建WPS在线表格连接"""
        try:
            return WpsHookClient(hook_url, token, time_out)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=False),
        ],
        outputList=[
            atomicMg.param("read_result", types="Any"),
        ],
    )
    def read_range(wps_client: WpsHookClient, sheet_name: str, range_address: str = ""):
        """读取区域数据

        range_address 规则:
        - 空: 读取整个 UsedRange
        - "3": 读取第 3 行
        - "A": 读取 A 列
        - "A2:D5": 读取显式区域
        """
        try:
            return wps_client.read(sheet_name, range_address or "")
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param("write_value", types="Any", required=True),
        ],
        outputList=[
            atomicMg.param("write_result", types="Any"),
        ],
    )
    def write_range(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        write_value,
    ):
        """写入数据（标量或二维列表，如 [["a","b"],["c","d"]]）"""
        try:
            return wps_client.write(sheet_name, range_address, write_value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param(
                "target_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("count_result", types="Int"),
        ],
    )
    def get_count(
        wps_client: WpsHookClient,
        sheet_name: str,
        target_type: TargetType = TargetType.ROW,
    ):
        """获取总行数/列数"""
        try:
            return wps_client.count(sheet_name, target_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param(
                "target_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("first_available_result", types="Any"),
        ],
    )
    def get_first_available(
        wps_client: WpsHookClient,
        sheet_name: str,
        target_type: TargetType = TargetType.ROW,
    ):
        """获取首个空行号/空列字母"""
        try:
            return wps_client.first_empty(sheet_name, target_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("image_result", types="Any"),
        ],
    )
    def get_image(wps_client: WpsHookClient, sheet_name: str, range_address: str):
        """获取单元格图片"""
        try:
            return wps_client.get_image(sheet_name, range_address)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param("image_source", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("insert_image_result", types="Bool"),
        ],
    )
    def insert_image(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        image_source: str,
    ):
        """插入图片（本地文件路径或 http/https 图片 URL）"""
        try:
            return wps_client.insert_image(sheet_name, range_address, image_source)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("hyperlink_result", types="Str"),
        ],
    )
    def get_hyperlink(wps_client: WpsHookClient, sheet_name: str, range_address: str):
        """获取单元格超链接"""
        try:
            return wps_client.get_hyperlink(sheet_name, range_address)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
        ],
        outputList=[
            atomicMg.param("sheet_names", types="List"),
        ],
    )
    def list_sheets(wps_client: WpsHookClient):
        """获取工作表列表"""
        try:
            return wps_client.list_sheets()
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("new_sheet_names", types="List", required=True),
        ],
        outputList=[
            atomicMg.param("created_sheets", types="List"),
        ],
    )
    def create_sheet(wps_client: WpsHookClient, new_sheet_names: list):
        """创建工作表（传入名称列表，如 ["Sheet2","Sheet3"]）"""
        try:
            return wps_client.create_sheets(new_sheet_names)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("delete_sheet_result", types="Bool"),
        ],
    )
    def delete_sheet(wps_client: WpsHookClient, sheet_name: str):
        """删除工作表"""
        try:
            return wps_client.delete_sheet(sheet_name)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)
