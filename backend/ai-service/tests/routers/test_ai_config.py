"""AI 配置中心测试: 掩码/合并/热更新语义 + 管理接口行为。

场景:
T1 掩码: 敏感键掩码(保留首尾4位), 非敏感键原样, is_masked 识别
T2 env 默认: 无 DB 行时返回 env/常量默认
T3 DB 覆盖 + 热更新: PUT 保存后 get(force) 立即生效
T4 白名单: 非法键被过滤; 掩码回传值跳过不覆盖
T5 管理接口: GET 掩码返回, PUT 保存, test 未配置上游返回 ok=False
T6 URL 安全校验: BASE_URL 非 http/https 拒绝落库
T7 resolve_upstream 去尾: base_url 误填完整 completions 地址时不双拼
T8 可选管理令牌: AI_CONFIG_ADMIN_TOKEN 配置后写操作须携带 X-Admin-Token
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.ai_config import AIConfig
from app.services import ai_config


@pytest_asyncio.fixture(autouse=True)
async def _test_session_factory(monkeypatch, test_db_engine):
    """指向测试 DB 引擎的会话工厂 + 每用例前后清空缓存与配置表。"""
    TestingSessionLocal = sessionmaker(bind=test_db_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(ai_config, "session_factory", TestingSessionLocal)

    async with TestingSessionLocal() as session:
        await session.execute(delete(AIConfig))
        await session.commit()
    ai_config._cache["data"] = None
    ai_config._cache["ts"] = 0.0

    yield

    async with TestingSessionLocal() as session:
        await session.execute(delete(AIConfig))
        await session.commit()
    ai_config._cache["data"] = None
    ai_config._cache["ts"] = 0.0


def test_mask_value():
    # T1: 敏感键掩码
    assert ai_config.mask_value("AICHAT_API_KEY", "sk-1234567890abcdef") == "sk-1***cdef"
    assert ai_config.mask_value("AICHAT_API_KEY", "short") == "***"
    assert ai_config.mask_value("AICHAT_API_KEY", "") == ""
    # T1: 非敏感键原样
    assert ai_config.mask_value("AICHAT_BASE_URL", "https://api.example.com/v1") == "https://api.example.com/v1"
    assert ai_config.mask_value("DEFAULT_MODEL", "maas/deepseek-v3.2") == "maas/deepseek-v3.2"
    # T1: is_masked
    assert ai_config.is_masked("sk-1***cdef") is True
    assert ai_config.is_masked("plain-value") is False


@pytest.mark.asyncio
async def test_get_ai_config_env_defaults():
    # T2: 无 DB 行时返回常量默认(纯配置键)
    config = await ai_config.get_ai_config(force=True)
    assert config[ai_config.DEFAULT_MODEL] == "maas/deepseek-v3.2"
    assert config[ai_config.SMART_MODEL] == "maas/deepseek-v3.2"
    assert config[ai_config.CUA_MODEL] == "doubao-seed-1-8-251228"
    assert ai_config.AICHAT_BASE_URL in config


@pytest.mark.asyncio
async def test_db_override_and_hot_update(client: AsyncClient):
    # T3/T4: PUT 保存 -> 立即生效; 非法键过滤
    response = await client.put(
        "/admin/ai-config",
        json={
            "values": {
                "AICHAT_BASE_URL": "https://llm.example.com/v1",
                "DEFAULT_MODEL": "maas/qwen3-235b",
                "NOT_A_KEY": "should-be-ignored",
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == "0000"
    assert "NOT_A_KEY" not in response.json()["data"]["saved_keys"]

    config = await ai_config.get_ai_config(force=True)
    assert config["AICHAT_BASE_URL"] == "https://llm.example.com/v1"
    assert config["DEFAULT_MODEL"] == "maas/qwen3-235b"

    # T4: 掩码值回传 = 未修改, 不落库
    await client.put(
        "/admin/ai-config",
        json={"values": {"AICHAT_API_KEY": "sk-1***cdef"}},
    )
    config = await ai_config.get_ai_config(force=True)
    assert config.get("AICHAT_API_KEY", "") != "sk-1***cdef"


@pytest.mark.asyncio
async def test_admin_ai_config_endpoints(client: AsyncClient):
    # T5: GET 掩码返回
    await client.put(
        "/admin/ai-config",
        json={"values": {"AICHAT_API_KEY": "sk-1234567890abcdef"}},
    )
    response = await client.get("/admin/ai-config")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["AICHAT_API_KEY"] == "sk-1***cdef"

    # T5: 未配置上游时 test 返回 ok=False(而非 5xx)
    response = await client.post("/admin/ai-config/test")
    assert response.status_code == 200
    assert response.json()["data"]["ok"] is False


@pytest.mark.asyncio
async def test_resolve_llm_endpoint(client: AsyncClient):
    await client.put(
        "/admin/ai-config",
        json={"values": {"AICHAT_BASE_URL": "https://llm.example.com/v1/"}},
    )
    _, endpoint = await ai_config.resolve_llm()
    assert endpoint == "https://llm.example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_set_ai_config_rejects_non_http_url(client: AsyncClient):
    # T6: BASE_URL 非 http/https 拒绝落库(服务层抛 ValueError, 接口返回 ERR)
    with pytest.raises(ValueError):
        await ai_config.set_ai_config({"AICHAT_BASE_URL": "file:///etc/passwd"})

    response = await client.put(
        "/admin/ai-config",
        json={"values": {"AICHAT_BASE_URL": "ftp://evil.example.com/v1"}},
    )
    assert response.status_code == 200
    assert response.json()["code"] != "0000"
    config = await ai_config.get_ai_config(force=True)
    assert config.get("AICHAT_BASE_URL", "") != "ftp://evil.example.com/v1"


@pytest.mark.asyncio
async def test_resolve_upstream_strips_duplicated_path(client: AsyncClient):
    # T7: base_url 误填完整 completions 地址时去尾, 不产生双拼路径
    await client.put(
        "/admin/ai-config",
        json={"values": {"AICHAT_BASE_URL": "https://llm.example.com/v1/chat/completions"}},
    )
    _, endpoint = await ai_config.resolve_llm()
    assert endpoint == "https://llm.example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_admin_token_guard(client: AsyncClient, monkeypatch):
    # T8: 配置令牌后无/错 token 拒绝写操作, 对的 token 放行; GET(只读)不受限
    from app.internal.admin import require_admin_token

    def _fake_settings():
        class _S:
            AI_CONFIG_ADMIN_TOKEN = "secret-token"
        return _S()

    monkeypatch.setattr("app.internal.admin.get_settings", _fake_settings)

    response = await client.put("/admin/ai-config", json={"values": {"DEFAULT_MODEL": "m"}})
    assert response.status_code == 403
    response = await client.put(
        "/admin/ai-config", json={"values": {}}, headers={"X-Admin-Token": "wrong"}
    )
    assert response.status_code == 403
    response = await client.post("/admin/ai-config/test", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 403

    response = await client.put(
        "/admin/ai-config",
        json={"values": {"DEFAULT_MODEL": "maas/qwen3-235b"}},
        headers={"X-Admin-Token": "secret-token"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == "0000"

    response = await client.get("/admin/ai-config")
    assert response.status_code == 200

    # 依赖自身语义验证
    with pytest.raises(Exception):
        await require_admin_token(None)
    await require_admin_token("secret-token")
