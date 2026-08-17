# Mock data
import httpx
import pytest
from httpx import AsyncClient

VALID_CHAT_REQUEST = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
    "temperature": 0.7,
    "max_tokens": 4096,
}

HEADER = {
    "X-User-Id": "2",
}


class FakeUpstreamResponse:
    """模拟上游 chat API 的非流式响应"""

    status_code = 200
    content = b'{"choices": [{"message": {"role": "assistant", "content": "Paris"}}]}'
    headers = {"content-type": "application/json"}
    text = content.decode()

    def raise_for_status(self):
        pass


class FakeStreamContext:
    """模拟上游 chat API 的流式响应 (async context manager)"""

    status_code = 200
    headers = {"content-type": "text/event-stream"}

    def raise_for_status(self):
        pass

    async def aiter_raw(self):
        yield b'data: {"choices": [{"delta": {"content": "Paris"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_upstream(monkeypatch):
    """mock httpx 外呼，避免测试依赖真实大模型服务。

    仅拦截发往假上游（AICHAT_BASE_URL=http://localhost:1）的请求；
    测试客户端自身的 ASGITransport 请求不受影响。
    """
    fake_host = "localhost:1"
    orig_post = httpx.AsyncClient.post
    orig_stream = httpx.AsyncClient.stream

    async def fake_post(self, url, *args, **kwargs):
        if fake_host not in str(url):
            return await orig_post(self, url, *args, **kwargs)
        return FakeUpstreamResponse()

    def fake_stream(self, method, url, *args, **kwargs):
        if fake_host not in str(url):
            return orig_stream(self, method, url, *args, **kwargs)
        return FakeStreamContext()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)


@pytest.mark.asyncio
async def test_chat_completion_non_stream(client: AsyncClient, mock_upstream):
    """Test the non-streaming chat completion endpoint"""
    request_data = VALID_CHAT_REQUEST.copy()
    request_data["stream"] = False

    response = await client.post("/v1/chat/completions", headers=HEADER, json=request_data)

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert (
        response.text.find("Paris") != -1
    )  # Check if the response contains the expected answer


@pytest.mark.asyncio
async def test_chat_completion_stream(client: AsyncClient, mock_upstream):
    """Test the streaming chat completion endpoint"""
    request_data = VALID_CHAT_REQUEST.copy()
    request_data["stream"] = True

    response = await client.post("/v1/chat/completions", headers=HEADER, json=request_data)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = b"".join(chunk for chunk in response.iter_bytes()).decode("utf-8")
    assert content.startswith("data: ")
    assert content.endswith("\n\n")
    assert "Paris" in content  # Check if the response contains the expected answer
