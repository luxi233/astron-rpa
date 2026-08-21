"""browser-bridge 通道安全校验。

WS 通道(ws://127.0.0.1:9082)与 /browser/transition 接口的安全加固逻辑集中在此模块,
保持纯函数无外部依赖, 便于单元测试覆盖。
"""

import os
import re
from base64 import b64decode

# 服务端保留的连接标识, 不允许客户端通过 token 注册为这些 uuid
RESERVED_UUIDS = {"$root$"}

# 扩展构建变体标识: $chrome$/$edge$/$firefox$/$360se$/$360ChromeX$/$chromium$/$unknown$ 等
_VARIANT_RE = re.compile(r"\$[\w-]+\$")


def validate_ws_token(token: str | None) -> str | None:
    """校验 WS 建连 token, 返回合法的连接标识(uuid), 非法返回 None。

    token 解码结果只允许两种合法形态:
    1) 扩展构建变体标识, 如 $chrome$/$firefox$;
    2) 浏览器原生 userAgent(以 Mozilla/ 开头, 兼容旧版扩展直接上报 UA)。
    拒绝任意字符串注册为 uuid, 避免本机其他进程伪造身份向已注入页面下发指令。
    """
    if not token:
        return None
    try:
        uuid = b64decode(token, validate=True).decode("utf-8")
    except Exception:
        return None
    if not uuid or uuid in RESERVED_UUIDS:
        return None
    if _VARIANT_RE.fullmatch(uuid) or uuid.startswith("Mozilla/"):
        return uuid
    return None


def resolve_inject_path(data_path: str, inject_root: str) -> str | None:
    """校验 /transition 的 data_path 仅指向 inject 目录内的文件。

    做路径规范化(realpath)防止 ../ 穿越与符号链接逃逸,
    避免该接口被用作任意本地文件读取。合法返回规范化路径, 否则返回 None。
    """
    if not data_path:
        return None
    real_root = os.path.realpath(inject_root)
    real_path = os.path.realpath(data_path)
    if real_path == real_root or not real_path.startswith(real_root + os.sep):
        return None
    return real_path
