"""
WPS 在线表格 AirScript Hook 核心客户端。

通过 WPS 金山文档 AirScript 脚本的 Webhook 端点读写在线表格：
- 先在 WPS 在线表格中部署配套的 AirScript 脚本并开启 Webhook
- 使用返回的 hook_url 与 AirScript-Token 建立连接
- 所有操作通过 HTTP POST 触发云端脚本执行
"""

import base64
import mimetypes
import os

import requests

ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_COUNT = "count"
ACTION_FIRST_EMPTY = "first_empty"
ACTION_GET_IMAGE = "get_image"
ACTION_INSERT_IMAGE = "insert_image"
ACTION_GET_HYPERLINK = "get_hyperlink"
ACTION_LIST_SHEETS = "list_sheets"
ACTION_CREATE_SHEET = "create_sheet"
ACTION_DELETE_SHEET = "delete_sheet"


class WpsHookError(Exception):
    """WPS Hook 调用异常。"""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.detail = detail


def build_payload(
    action,
    sheet_name="",
    range_address="",
    write_value=None,
    target_type="row",
    new_sheet_names=None,
    image_data="",
):
    """按 AirScript 约定的 Context 结构构造请求体。"""
    return {
        "Context": {
            "sheet_name": sheet_name,
            "argv": {
                "action": action,
                "data": [],
                "sheet_name": sheet_name,
                "range_address": range_address,
                "write_value": write_value if write_value is not None else "",
                "target_type": target_type,
                "new_sheet_names": new_sheet_names if new_sheet_names is not None else [],
                "image_data": image_data,
            },
        }
    }


def is_http_url(value):
    """当输入是 HTTP 或 HTTPS URL 时返回 True。"""
    text = str(value).strip().lower()
    return text.startswith("http://") or text.startswith("https://")


def file_to_data_uri(file_path):
    """把本地图片文件转换为 data URI 字符串。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as file_handle:
        encoded_bytes = base64.b64encode(file_handle.read()).decode("ascii")

    return f"data:{mime_type};base64,{encoded_bytes}"


def normalize_image_source(image_source):
    """把图片输入规范成 InsertImage 可接受的 URL 或 data URI。"""
    if image_source is None:
        raise WpsHookError("image_source is required", "图片来源不能为空")

    source_text = str(image_source).strip()
    if not source_text:
        raise WpsHookError("image_source is required", "图片来源不能为空")

    if is_http_url(source_text):
        return source_text

    if not os.path.isfile(source_text):
        raise WpsHookError(f"FileNotFoundError: {source_text}", "本地图片文件不存在")

    return file_to_data_uri(source_text)


def normalize_sheet_names(new_sheet_names):
    """把工作表名称输入规范成列表。"""
    if new_sheet_names is None:
        return []
    if isinstance(new_sheet_names, (list, tuple)):
        return [str(name) for name in new_sheet_names]
    text = str(new_sheet_names).strip()
    if not text:
        return []
    return [text]


class WpsHookClient:
    """WPS AirScript Hook 连接对象，可复用执行多个操作。"""

    def __init__(self, hook_url: str, token: str, timeout: int = 30):
        if not hook_url:
            raise WpsHookError("hook_url is required", "Webhook 地址不能为空")
        if not token:
            raise WpsHookError("token is required", "AirScript-Token 不能为空")

        self.hook_url = hook_url
        self.token = token
        self.timeout = timeout if timeout and int(timeout) > 0 else 30

    def send_request(self, action, **kwargs):
        """发送一次 Hook 请求并返回脚本结果。"""
        payload = build_payload(action, **kwargs)
        headers = {
            "Content-Type": "application/json",
            "AirScript-Token": self.token,
        }
        try:
            response = requests.post(
                self.hook_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise WpsHookError(f"Request failed: {e}", "WPS Hook 请求失败，请检查网络与 Webhook 地址")

        if response.status_code != 200:
            raise WpsHookError(
                f"HTTP {response.status_code}: {response.text[:200]}",
                "WPS Hook 返回异常状态码",
            )

        try:
            response_json = response.json()
        except ValueError:
            raise WpsHookError(f"Invalid JSON: {response.text[:200]}", "WPS Hook 返回了非 JSON 内容")

        if response_json.get("code") not in (None, 0, 200, "0", "200"):
            raise WpsHookError(
                f"WPS error {response_json.get('code')}: {response_json.get('msg') or response_json.get('message')}",
                "WPS AirScript 脚本执行失败",
            )

        data = response_json.get("data") or {}
        return data.get("result")

    # ---- 业务操作 ----

    def read(self, sheet_name, range_address=""):
        """读取工作表数据。range_address 支持 ""（整表）、"3"（第3行）、"A"（A列）、"A2:D5"。"""
        return self.send_request(
            ACTION_READ,
            sheet_name=sheet_name,
            range_address=range_address,
        )

    def write(self, sheet_name, range_address, write_value):
        """从指定起点写入标量或二维列表。"""
        return self.send_request(
            ACTION_WRITE,
            sheet_name=sheet_name,
            range_address=range_address,
            write_value=write_value,
        )

    def count(self, sheet_name, target_type="row"):
        """返回 UsedRange 的总行数或总列数。"""
        return self.send_request(
            ACTION_COUNT,
            sheet_name=sheet_name,
            target_type=target_type,
        )

    def first_empty(self, sheet_name, target_type="row"):
        """返回首个可用行号或列字母。"""
        return self.send_request(
            ACTION_FIRST_EMPTY,
            sheet_name=sheet_name,
            target_type=target_type,
        )

    def get_image(self, sheet_name, range_address):
        """返回目标单元格关联图片的数据。"""
        return self.send_request(
            ACTION_GET_IMAGE,
            sheet_name=sheet_name,
            range_address=range_address,
        )

    def insert_image(self, sheet_name, range_address, image_source):
        """通过本地文件或 URL 向目标单元格插入图片。"""
        return self.send_request(
            ACTION_INSERT_IMAGE,
            sheet_name=sheet_name,
            range_address=range_address,
            image_data=normalize_image_source(image_source),
        )

    def get_hyperlink(self, sheet_name, range_address):
        """返回目标单元格的超链接地址。"""
        return self.send_request(
            ACTION_GET_HYPERLINK,
            sheet_name=sheet_name,
            range_address=range_address,
        )

    def list_sheets(self):
        """返回当前工作簿中的所有工作表名称。"""
        return self.send_request(ACTION_LIST_SHEETS)

    def create_sheets(self, new_sheet_names):
        """创建一个或多个工作表并返回最终名称。"""
        return self.send_request(
            ACTION_CREATE_SHEET,
            new_sheet_names=normalize_sheet_names(new_sheet_names),
        )

    def delete_sheet(self, sheet_name):
        """删除指定工作表。"""
        return self.send_request(
            ACTION_DELETE_SHEET,
            sheet_name=sheet_name,
        )
