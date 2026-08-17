import random

import pytest
from httpx import AsyncClient

# 为 API Key 相关接口添加用户 ID 认证
USER_ID_HEADER = {"X-User-Id": "1234"}

# 实际路由: /api-keys/get | /api-keys/create | /api-keys/remove (非 RESTful)


@pytest.mark.asyncio
async def test_get_all_api_keys(client: AsyncClient):
    """Test getting all API keys."""
    response = await client.get("/api-keys/get", headers=USER_ID_HEADER)
    assert response.status_code == 200

    data = response.json()
    assert "data" in data
    assert "records" in data["data"]
    assert isinstance(data["data"]["records"], list)

    # Check structure of API keys if any exist
    if data["data"]["records"]:
        api_key = data["data"]["records"][0]
        assert "id" in api_key
        assert "name" in api_key
        assert "createTime" in api_key


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient):
    """Test creating a new API key."""
    random_suffix = random.randint(1000, 9999)

    api_key_data = {"name": f"Test API Key {random_suffix}"}

    response = await client.post("/api-keys/create", json=api_key_data, headers=USER_ID_HEADER)
    assert response.status_code == 201

    data = response.json()
    # create 接口返回 data.api_key 为明文 key（仅此一次可见）
    assert "data" in data
    assert "api_key" in data["data"]
    assert len(data["data"]["api_key"]) > 8


@pytest.mark.asyncio
async def test_delete_api_key(client: AsyncClient):
    """Test deleting an API key."""
    # First create an API key to ensure we have one to delete
    api_key_data = {"name": f"API Key to Delete {random.randint(1000, 9999)}"}

    create_response = await client.post("/api-keys/create", json=api_key_data, headers=USER_ID_HEADER)
    assert create_response.status_code == 201

    plain_key = create_response.json()["data"]["api_key"]
    prefix = plain_key[:8]

    # 查询列表拿到自增 id
    list_response = await client.get("/api-keys/get", headers=USER_ID_HEADER)
    assert list_response.status_code == 200
    records = list_response.json()["data"]["records"]
    matched = [r for r in records if r["api_key"].startswith(prefix)]
    assert matched, "created key should appear in list"
    api_key_id = matched[0]["id"]

    # Now delete the API key (POST /remove with body)
    delete_response = await client.post("/api-keys/remove", json={"id": api_key_id}, headers=USER_ID_HEADER)
    assert delete_response.status_code == 200

    # Verify it's gone by getting all API keys and checking
    all_keys_response = await client.get("/api-keys/get", headers=USER_ID_HEADER)
    assert all_keys_response.status_code == 200

    all_keys = all_keys_response.json()["data"]["records"]
    assert not any(key["id"] == api_key_id for key in all_keys)


@pytest.mark.asyncio
async def test_delete_nonexistent_api_key(client: AsyncClient):
    """Test deleting a non-existent API key."""
    non_existent_id = random.randint(10000, 99999)
    response = await client.post("/api-keys/remove", json={"id": non_existent_id}, headers=USER_ID_HEADER)

    # 删除不存在记录时接口返回 200 + ERR code（幂等语义）
    assert response.status_code == 200
    assert response.json()["code"] != "0000"
