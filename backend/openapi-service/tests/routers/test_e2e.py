import random

import pytest
from httpx import AsyncClient

# E2E 数据流（不含依赖 WebSocket 执行器的真实运行，那属于 L3 集成测试）:
# upsert 工作流 → 列表 → 详情 → execute 校验 → executions 列表
USER_ID_HEADER = {"X-User-Id": "1234"}


@pytest.mark.asyncio
async def test_workflow_dataflow_e2e(client: AsyncClient, api_key):
    """Workflow CRUD + execution precheck dataflow across routers."""
    auth_headers = {"Authorization": f"Bearer {api_key['key']}"}
    project_id = f"e2e-{random.randint(10000, 99999)}"

    # 1. upsert 创建工作流
    payload = {
        "project_id": project_id,
        "name": "E2E Workflow",
        "version": 1,
        "status": 1,
        "parameters": "[]",
    }
    upsert_response = await client.post("/workflows/upsert", json=payload, headers=USER_ID_HEADER)
    assert upsert_response.status_code == 200
    assert upsert_response.json()["code"] == "0000"

    # 2. 列表可见
    list_response = await client.get("/workflows/get", headers=USER_ID_HEADER)
    assert list_response.status_code == 200
    records = list_response.json()["data"]["records"]
    assert any(r["project_id"] == project_id for r in records)

    # 3. 详情正确
    detail_response = await client.get(f"/workflows/get/{project_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["workflow"]["project_id"] == project_id

    # 4. API Key 鉴权预检：对不存在的工作流执行应返回 ERR（真实执行依赖 WebSocket 执行器，属 L3 集成）
    execution_data = {"project_id": f"non-existent-{random.randint(10000, 99999)}", "params": {"e2e": True}}
    execute_response = await client.post("/workflows/execute-async", json=execution_data, headers=auth_headers)
    assert execute_response.status_code == 202
    assert execute_response.json()["code"] != "0000"

    # 5. executions 路由可达
    exec_list_response = await client.get("/executions/get", headers=auth_headers)
    assert exec_list_response.status_code == 200


@pytest.mark.asyncio
async def test_api_key_roundtrip_e2e(client: AsyncClient):
    """API Key create → list → remove roundtrip via public routes."""
    create_response = await client.post(
        "/api-keys/create", json={"name": f"e2e-key-{random.randint(1000, 9999)}"}, headers=USER_ID_HEADER
    )
    assert create_response.status_code == 201
    plain_key = create_response.json()["data"]["api_key"]

    list_response = await client.get("/api-keys/get", headers=USER_ID_HEADER)
    assert list_response.status_code == 200
    records = list_response.json()["data"]["records"]
    assert any(r["api_key"].startswith(plain_key[:8]) for r in records)

    # 明文 key 可用于 Bearer 鉴权访问受保护接口
    auth_response = await client.get("/executions/get", headers={"Authorization": f"Bearer {plain_key}"})
    assert auth_response.status_code == 200


@pytest.mark.asyncio
async def test_complex_parameters_roundtrip(client: AsyncClient):
    """Upsert workflow with complex parameter types and read back."""
    complex_params = [
        {"varName": "string_param", "varValue": "text"},
        {"varName": "number_param", "varValue": 42},
        {"varName": "bool_param", "varValue": True},
        {"varName": "array_param", "varValue": [1, 2, 3]},
    ]
    import json as _json

    payload = {
        "project_id": f"complex-{random.randint(10000, 99999)}",
        "name": "Complex Params Workflow",
        "version": 1,
        "status": 1,
        "parameters": _json.dumps(complex_params, ensure_ascii=False),
    }
    response = await client.post("/workflows/upsert", json=payload, headers=USER_ID_HEADER)
    assert response.status_code == 200

    detail = await client.get(f"/workflows/get/{payload['project_id']}")
    assert detail.status_code == 200
    stored = detail.json()["data"]["workflow"]["parameters"]
    parsed = _json.loads(stored) if isinstance(stored, str) else stored
    assert {p["varName"] for p in parsed} == {"string_param", "number_param", "bool_param", "array_param"}
