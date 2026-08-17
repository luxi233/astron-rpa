import random

import pytest
from httpx import AsyncClient

# 实际路由: GET /executions/get (列表) | GET /executions/{execution_id} (详情)


@pytest.mark.asyncio
async def test_get_executions_empty(client: AsyncClient, api_key):
    """Test listing executions for a fresh user returns empty page."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}
    response = await client.get("/executions/get", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["total"] == 0
    assert data["executions"] == []
    assert data["pageNo"] == 1


@pytest.mark.asyncio
async def test_get_execution_not_found(client: AsyncClient, api_key):
    """Test getting a non-existent execution returns ERR code (200 by design)."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}
    non_existent_id = f"non-existent-{random.randint(10000, 99999)}"
    response = await client.get(f"/executions/{non_existent_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["code"] != "0000"
    assert non_existent_id in body["msg"]


@pytest.mark.asyncio
async def test_execution_record_lifecycle(client: AsyncClient, api_key, test_get_db):
    """Test execution record via service layer then read back through the API.

    真实执行链路依赖 WebSocket 执行器（L3 集成范畴），单测只验证
    记录创建/状态更新与查询路由的契约。
    """
    from app.schemas.workflow import ExecutionCreate
    from app.services.execution import ExecutionService

    user_id = "1234"
    service = ExecutionService(test_get_db)
    created = await service.create_execution(
        ExecutionCreate(project_id=f"proj-{random.randint(1000, 9999)}", params={"k": "v"}), user_id
    )
    assert created.status == "PENDING"

    headers = {"Authorization": f"Bearer {api_key['key']}"}
    detail_response = await client.get(f"/executions/{created.id}", headers=headers)
    assert detail_response.status_code == 200
    execution = detail_response.json()["data"]["execution"]
    assert execution["id"] == created.id
    assert execution["status"] == "PENDING"

    list_response = await client.get("/executions/get", headers=headers)
    assert list_response.status_code == 200
    data = list_response.json()["data"]
    assert data["total"] >= 1
    assert any(e["id"] == created.id for e in data["executions"])


@pytest.mark.asyncio
async def test_execution_requires_api_key(client: AsyncClient):
    """Test that executions endpoints reject requests without API key."""
    response = await client.get("/executions/get")
    assert response.status_code in (401, 403)
