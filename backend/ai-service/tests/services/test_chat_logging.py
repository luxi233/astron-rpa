import logging
from unittest.mock import patch

import pytest

from app.schemas.chat import ChatCompletionParam
from app.services.chat import chat_completions

UPSTREAM_KEY = "secret-upstream-key-9f3c"
CONTENT_MARKER = "USER_MESSAGE_MARKER_42Q7"


class _FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    content = b'{"id": "chatcmpl-1"}'

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        return _FakeResponse()


@pytest.mark.asyncio
async def test_chat_completions_does_not_log_key_or_message_body(caplog):
    params = ChatCompletionParam(
        model="deepseek-chat",
        stream=False,
        messages=[{"role": "user", "content": f"private payload {CONTENT_MARKER}"}],
    )

    fake_client = _FakeAsyncClient()
    with (
        caplog.at_level(logging.DEBUG, logger="app.services.chat"),
        patch("app.services.chat.httpx.AsyncClient", return_value=fake_client),
    ):
        await chat_completions(
            params, key=UPSTREAM_KEY, endpoint="https://upstream.test/chat/completions"
        )

    rendered = "\n".join(rec.getMessage() for rec in caplog.records)

    # The credential must still be sent upstream, but never written to logs.
    assert fake_client.post_calls, "upstream request was not made"
    sent_headers = fake_client.post_calls[0]["headers"]
    assert sent_headers["Authorization"] == f"Bearer {UPSTREAM_KEY}"

    assert UPSTREAM_KEY not in rendered
    assert CONTENT_MARKER not in rendered
