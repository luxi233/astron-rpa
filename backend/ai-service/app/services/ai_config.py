"""AI 配置中心: 环境变量默认 + DB 覆盖 + 进程内短 TTL 缓存, 支持不重启热更新。

背景: 旧实现的 AICHAT_API_KEY 等在模块 import 时固化为常量, 且 get_settings 带
lru_cache, 修改配置必须重启容器(4 worker)。本服务把可变配置下沉到 ai_configs 表,
每次请求现读(TTL 秒级缓存), 管理接口写入后全部 worker 在 TTL 内收敛到新值。
"""

import time

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.logger import get_logger
from app.models.ai_config import AIConfig

logger = get_logger(__name__)

# ---- 可配置键定义 ----
# env 同名变量作为默认值, DB 行存在时覆盖
AICHAT_BASE_URL = "AICHAT_BASE_URL"
AICHAT_API_KEY = "AICHAT_API_KEY"
CUA_BASE_URL = "CUA_BASE_URL"
CUA_API_KEY = "CUA_API_KEY"
# 纯配置键(无 env 对应)
DEFAULT_MODEL = "DEFAULT_MODEL"
SMART_MODEL = "SMART_MODEL"
CUA_MODEL = "CUA_MODEL"

ENV_BACKED_KEYS = (AICHAT_BASE_URL, AICHAT_API_KEY, CUA_BASE_URL, CUA_API_KEY)
CONFIG_KEYS = ENV_BACKED_KEYS + (DEFAULT_MODEL, SMART_MODEL, CUA_MODEL)

CONSTANT_DEFAULTS = {
    DEFAULT_MODEL: "maas/deepseek-v3.2",
    SMART_MODEL: "maas/deepseek-v3.2",
    CUA_MODEL: "doubao-seed-1-8-251228",
}

# 敏感键: 键名小写包含以下子串时, 管理接口返回掩码值
SENSITIVE_KEYWORDS = ("key", "secret", "token")
MASK_MARK = "***"

# 测试可替换的会话工厂(monkeypatch ai_config.session_factory)
session_factory = AsyncSessionLocal

_cache: dict = {"ts": 0.0, "data": None}
_CACHE_TTL = 3.0


def _env_defaults() -> dict:
    settings = get_settings()
    return {key: getattr(settings, key, "") or "" for key in ENV_BACKED_KEYS}


def _is_sensitive(key: str) -> bool:
    return any(kw in key.lower() for kw in SENSITIVE_KEYWORDS)


def mask_value(key: str, value: str) -> str:
    """敏感值掩码: 保留首尾各 4 位便于辨认, 短值全掩码; 非敏感值原样返回。"""
    if not _is_sensitive(key) or not value:
        return value
    if len(value) <= 8:
        return MASK_MARK
    return f"{value[:4]}{MASK_MARK}{value[-4:]}"


def is_masked(value: str) -> bool:
    """识别管理接口回传的掩码值(保存时跳过, 避免掩码覆盖真实 key)。"""
    return isinstance(value, str) and MASK_MARK in value


async def get_ai_config(force: bool = False) -> dict:
    """读取当前生效配置: env 默认 + DB 覆盖, 进程内 TTL 缓存。"""
    now = time.monotonic()
    if not force and _cache["data"] is not None and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    config = _env_defaults()
    config.update(CONSTANT_DEFAULTS)

    try:
        async with session_factory() as session:
            rows = (await session.execute(select(AIConfig))).scalars().all()
            for row in rows:
                if row.config_key in CONFIG_KEYS and row.config_value != "":
                    config[row.config_key] = row.config_value
    except Exception as e:  # DB 不可达时退回 env 默认, 不阻断 AI 请求链路
        logger.warning("读取 AI 配置表失败, 回退环境变量默认: %s", e)

    _cache["data"] = config
    _cache["ts"] = time.monotonic()
    return config


URL_KEYS = (AICHAT_BASE_URL, CUA_BASE_URL)


def _validate_url(key: str, value: str) -> None:
    """BASE_URL 仅允许 http/https(阻断把上游指向任意 scheme 的滥用面), 非法值拒绝落库。"""
    if key in URL_KEYS and value and not value.lower().startswith(("http://", "https://")):
        raise ValueError(f"{key} 仅支持 http/https 地址: {value}")


async def set_ai_config(values: dict) -> dict:
    """写入配置(白名单过滤, 掩码值跳过), 写入后立即失效缓存; 非法值抛 ValueError 由调用方拒绝。"""
    saved = {}
    async with session_factory() as session:
        for key, value in values.items():
            if key not in CONFIG_KEYS:
                continue
            if not isinstance(value, str):
                value = str(value)
            if is_masked(value):
                # 回传的掩码值视为"未修改", 不落库
                continue
            _validate_url(key, value)
            row = await session.get(AIConfig, key)
            if row is None:
                row = AIConfig(config_key=key, config_value=value)
                session.add(row)
            else:
                row.config_value = value
            saved[key] = value
        await session.commit()

    await get_ai_config(force=True)
    return saved


async def resolve_upstream(path: str) -> tuple[str, str]:
    """解析上游 LLM 接入点, 返回 (api_key, endpoint)。"""
    config = await get_ai_config()
    base_url = config.get(AICHAT_BASE_URL, "").rstrip("/")
    # 用户误把完整接口地址填进 base_url(如 .../v1/chat/completions)时去尾, 防止双拼路径 404
    suffix = f"/{path.lstrip('/')}"
    if base_url.endswith(suffix):
        base_url = base_url[: -len(suffix)]
    endpoint = f"{base_url}/{path.lstrip('/')}" if base_url else ""
    return config.get(AICHAT_API_KEY, ""), endpoint


async def resolve_llm() -> tuple[str, str]:
    """解析统一大模型(chat/completions)上游。"""
    return await resolve_upstream("chat/completions")
