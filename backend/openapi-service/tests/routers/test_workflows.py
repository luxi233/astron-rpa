import random

import pytest
from httpx import AsyncClient

# 实际路由: /workflows/upsert | /workflows/get | /workflows/get/{id} | /workflows/execute | /workflows/execute-async
USER_ID_HEADER = {"X-User-Id": "1234"}


def _workflow_payload(project_id: str | None = None):
    return {
        "project_id": project_id or f"proj-{random.randint(10000, 99999)}",
        "name": "Test Workflow",
        "version": 1,
        "status": 1,
        "parameters": '[{"varName": "p1", "varValue": "v1"}]',
    }


@pytest.mark.asyncio
async def test_upsert_and_get_workflow(client: AsyncClient):
    """Test creating a workflow via upsert and reading it back."""
    payload = _workflow_payload()

    # 创建
    create_response = await client.post("/workflows/upsert", json=payload, headers=USER_ID_HEADER)
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["code"] == "0000"
    assert body["data"]["action"] == "created"
    assert body["data"]["workflow"]["project_id"] == payload["project_id"]

    # 更新（同 project_id 再次 upsert）
    payload["name"] = "Renamed Workflow"
    update_response = await client.post("/workflows/upsert", json=payload, headers=USER_ID_HEADER)
    assert update_response.status_code == 200
    assert update_response.json()["data"]["action"] == "updated"

    # 列表可见
    list_response = await client.get("/workflows/get", headers=USER_ID_HEADER)
    assert list_response.status_code == 200
    records = list_response.json()["data"]["records"]
    assert any(r["project_id"] == payload["project_id"] for r in records)

    # 详情
    detail_response = await client.get(f"/workflows/get/{payload['project_id']}")
    assert detail_response.status_code == 200
    workflow = detail_response.json()["data"]["workflow"]
    assert workflow["project_id"] == payload["project_id"]
    assert workflow["name"] == "Renamed Workflow"


@pytest.mark.asyncio
async def test_get_nonexistent_workflow(client: AsyncClient):
    """Test getting a non-existent workflow returns SUCCESS with null data (by design)."""
    non_existent_id = f"non-existent-{random.randint(10000, 99999)}"
    response = await client.get(f"/workflows/get/{non_existent_id}")
    assert response.status_code == 200
    body = response.json()
    # 设计上返回 SUCCESS + data=None，由前端处理 not found
    assert body["data"] is None
    assert non_existent_id in body["msg"]


@pytest.mark.asyncio
async def test_execute_workflow_not_found(client: AsyncClient, api_key):
    """Test executing a non-existent workflow returns ERR code."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}
    execution_data = {"project_id": f"non-existent-{random.randint(10000, 99999)}", "params": {"k": "v"}}

    response = await client.post("/workflows/execute", json=execution_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["code"] != "0000"
    assert "not found" in response.json()["msg"].lower()


@pytest.mark.asyncio
async def test_execute_workflow_async_not_found(client: AsyncClient, api_key):
    """Test async executing a non-existent workflow returns ERR code."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}
    execution_data = {"project_id": f"non-existent-{random.randint(10000, 99999)}", "params": {"k": "v"}}

    response = await client.post("/workflows/execute-async", json=execution_data, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_execution_status(client: AsyncClient, api_key):
    """Test getting execution status."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}

    # First, execute a workflow asynchronously to get an execution ID
    list_response = await client.get("/workflows/get", headers=headers)
    assert list_response.status_code == 200

    all_workflows = list_response.json()["data"]["records"]
    if not all_workflows:
        pytest.skip("No workflows available for testing")

    # Find an active workflow
    active_workflow = next((w for w in all_workflows if w["status"] == 1), None)
    if not active_workflow:
        pytest.skip("No active workflows available for testing")

    # Execute the workflow asynchronously
    project_id = active_workflow["project_id"]
    execution_data = {"project_id": project_id, "params": {"test_param": "test_value"}}

    execute_response = await client.post("/workflows/execute-async", json=execution_data, headers=headers)
    assert execute_response.status_code == 202

    execution_id = execute_response.json()["data"]["executionId"]

    # Get the execution status
    status_response = await client.get(f"/executions/{execution_id}", headers=headers)
    assert status_response.status_code == 200

    data = status_response.json()["data"]["execution"]
    assert data["id"] == execution_id
    assert data["project_id"] == project_id
    assert "status" in data
    assert data["status"] in ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "UNKNOWN", "TIMEOUT"]


@pytest.mark.asyncio
async def test_get_nonexistent_execution(client: AsyncClient, api_key):
    """Test getting a non-existent execution."""
    headers = {"Authorization": f"Bearer {api_key['key']}"}

    # Using a random ID that's unlikely to exist
    non_existent_id = f"non-existent-{random.randint(10000, 99999)}"
    response = await client.get(f"/executions/{non_existent_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "5001"
    assert "not found" in response.json()["msg"].lower()
