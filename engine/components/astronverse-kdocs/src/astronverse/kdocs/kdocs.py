from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.kdocs import ClearType, FitType, FormulaMode, FuncName, MergeType, OpType, TargetType
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
            atomicMg.param(
                "read_display",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("read_result", types="Any"),
        ],
    )
    def read_range(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str = "",
        read_display: bool = False,
    ):
        """读取区域数据

        range_address 规则:
        - 空: 读取整个 UsedRange
        - "3": 读取第 3 行
        - "A": 读取 A 列
        - "A2:D5": 读取显式区域

        read_display=True 时读取单元格实际显示文本（日期、百分比等按显示格式返回），
        默认读取原始值（日期列自动转换为 "YYYY-MM-DD HH:mm:ss" 字符串）。
        """
        try:
            return wps_client.read(sheet_name, range_address or "", read_display)
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

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=False),
            atomicMg.param("find_text", types="Str", required=True),
            atomicMg.param("replace_text", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("replace_result", types="Bool"),
        ],
    )
    def replace(
        wps_client: WpsHookClient, sheet_name: str, range_address: str = "", find_text: str = "", replace_text: str = ""
    ):
        """查找替换

        range_address 为空时在整个已使用区域内查找替换
        """
        try:
            return wps_client.replace(sheet_name, find_text, replace_text, range_address or "")
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("source_sheet", types="Str", required=True),
            atomicMg.param("source_range", types="Str", required=True),
            atomicMg.param("target_sheet", types="Str", required=False),
            atomicMg.param("target_range", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("copy_paste_result", types="Bool"),
        ],
    )
    def copy_paste(
        wps_client: WpsHookClient,
        source_sheet: str,
        source_range: str,
        target_sheet: str = "",
        target_range: str = "A1",
    ):
        """复制粘贴区域（支持跨工作表）"""
        try:
            return wps_client.copy_paste(source_sheet, source_range, target_sheet or source_sheet, target_range)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param(
                "op_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("insert_cells_result", types="Bool"),
        ],
    )
    def insert_cells(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        op_type: OpType = OpType.ROW,
    ):
        """插入行/列/单元格

        op_type: row 在目标位置插入行；column 插入列；cell 插入单元格
        """
        try:
            return wps_client.insert_cells(sheet_name, range_address, op_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param(
                "op_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("delete_cells_result", types="Bool"),
        ],
    )
    def delete_cells(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        op_type: OpType = OpType.ROW,
    ):
        """删除行/列/单元格

        op_type: row 删除目标位置所在行；column 删除列；cell 删除单元格
        """
        try:
            return wps_client.delete_cells(sheet_name, range_address, op_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=False),
            atomicMg.param(
                "clear_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("clear_range_result", types="Bool"),
        ],
    )
    def clear_range(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str = "",
        clear_type: ClearType = ClearType.CONTENTS,
    ):
        """清除区域内容

        clear_type: contents 仅清除内容；formats 仅清除格式；all 清除内容和格式
        """
        try:
            return wps_client.clear_range(sheet_name, range_address or "", clear_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param(
                "merge_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("merge_cells_result", types="Bool"),
        ],
    )
    def merge_cells(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        merge_type: MergeType = MergeType.MERGE,
    ):
        """合并/拆分单元格"""
        try:
            return wps_client.merge_cells(sheet_name, range_address, merge_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param("format_options", types="Any", required=True),
        ],
        outputList=[
            atomicMg.param("set_format_result", types="Bool"),
        ],
    )
    def set_format(wps_client: WpsHookClient, sheet_name: str, range_address: str, format_options):
        """设置单元格格式

        format_options 为字典，支持的键: font_bold/font_italic/font_size/font_name/font_color/bg_color/h_align/v_align/wrap_text/number_format，
        如 {"bg_color":"#FFFF00","font_bold":true,"h_align":"center"}
        """
        try:
            return wps_client.set_format(sheet_name, range_address, format_options)
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
            atomicMg.param("color_result", types="Any"),
        ],
    )
    def get_color(wps_client: WpsHookClient, sheet_name: str, range_address: str):
        """获取单元格颜色

        返回字典，如 {"bg_color":"#FFFFFF","font_color":"#000000"}
        """
        try:
            return wps_client.get_color(sheet_name, range_address)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=True),
            atomicMg.param(
                "formula_mode",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
            atomicMg.param("formula_text", types="Str", required=False),
        ],
        outputList=[
            atomicMg.param("formula_result", types="Any"),
        ],
    )
    def formula(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str,
        formula_mode: FormulaMode = FormulaMode.GET,
        formula_text: str = "",
    ):
        """读写公式

        formula_mode: get 读取区域左上角单元格公式；set 写入公式（需同时填写公式内容）
        """
        try:
            return wps_client.formula(
                sheet_name,
                range_address,
                formula_text,
                formula_mode == FormulaMode.SET,
            )
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
        ],
        outputList=[
            atomicMg.param("save_workbook_result", types="Bool"),
        ],
    )
    def save_workbook(wps_client: WpsHookClient):
        """保存文档（保存当前工作簿的全部改动）"""
        try:
            return wps_client.save_workbook()
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("new_sheet_name", types="Str", required=True),
        ],
        outputList=[
            atomicMg.param("rename_sheet_result", types="Str"),
        ],
    )
    def rename_sheet(wps_client: WpsHookClient, sheet_name: str, new_sheet_name: str):
        """重命名工作表"""
        try:
            return wps_client.rename_sheet(sheet_name, new_sheet_name)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("position", types="Int", required=True),
        ],
        outputList=[
            atomicMg.param("move_sheet_result", types="Bool"),
        ],
    )
    def move_sheet(wps_client: WpsHookClient, sheet_name: str, position: int):
        """移动工作表（position 为目标位置，从 1 开始）"""
        try:
            return wps_client.move_sheet(sheet_name, position)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=False),
            atomicMg.param(
                "fit_type",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("auto_fit_result", types="Bool"),
        ],
    )
    def auto_fit(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str = "",
        fit_type: FitType = FitType.BOTH,
    ):
        """行列自适应（自动调整行高/列宽）

        fit_type: row 调整行高；column 调整列宽；both 两者都调整。区域为空时对整个已使用区域生效
        """
        try:
            return wps_client.auto_fit(sheet_name, range_address or "", fit_type.value)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
        ],
        outputList=[
            atomicMg.param("file_info_result", types="Any"),
        ],
    )
    def get_file_info(wps_client: WpsHookClient):
        """获取文档信息

        返回字典，包含 file（文档信息）与 user（当前用户信息）
        """
        try:
            return wps_client.get_file_info()
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)

    @staticmethod
    @atomicMg.atomic(
        "WPS",
        inputList=[
            atomicMg.param("wps_client", types="Any", required=True),
            atomicMg.param("sheet_name", types="Str", required=True),
            atomicMg.param("range_address", types="Str", required=False),
            atomicMg.param(
                "func_name",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
                required=False,
            ),
            atomicMg.param("k", types="Int", required=False),
        ],
        outputList=[
            atomicMg.param("calc_result", types="Any"),
        ],
    )
    def calc_function(
        wps_client: WpsHookClient,
        sheet_name: str,
        range_address: str = "",
        func_name: FuncName = FuncName.SUM,
        k: int = 1,
    ):
        """工作表函数计算

        func_name: sum 求和 / average 平均 / min 最小 / max 最大 / large 第k大 / small 第k小（large、small 需填写 k）
        """
        try:
            return wps_client.calc_function(sheet_name, range_address or "", func_name.value, k)
        except WpsHookError as e:
            raise BaseException(str(e), e.detail)
