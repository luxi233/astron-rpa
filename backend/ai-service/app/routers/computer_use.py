import json
from urllib.parse import urljoin

from fastapi import APIRouter, Body, HTTPException

from app.models.smart_component import SmartChatResponse
from app.schemas.chat import ChatCompletionParam
from app.services import ai_config
from app.services.chat import chat_completions

router = APIRouter(
    prefix="/cua",
    tags=["计算机使用代理"],
)


async def _resolve_cua() -> tuple[str, str, str]:
    """每请求现读配置(热更新), 返回 (key, endpoint, model)。"""
    config = await ai_config.get_ai_config()
    base_url = config.get(ai_config.CUA_BASE_URL, "")
    api_key = config.get(ai_config.CUA_API_KEY, "")
    model = config.get(ai_config.CUA_MODEL, "")
    endpoint = urljoin(f"{base_url.rstrip('/')}/", "chat/completions") if base_url else ""
    if not endpoint:
        raise HTTPException(status_code=503, detail="CUA 上游未配置, 请在 AI 设置中配置 CUA_BASE_URL")
    return api_key, endpoint, model


@router.post("/chat/stream")
async def cua_chat_stream(messages: list[dict] = Body(...)):
    cua_key, cua_endpoint, cua_model = await _resolve_cua()
    llm_params = ChatCompletionParam(
        model=cua_model,
        stream=True,
        temperature=0,
        max_tokens=8192,
        messages=messages,
    )

    return await chat_completions(llm_params, cua_key, cua_endpoint)


@router.post("/chat", response_model=SmartChatResponse)
async def cua_chat(messages: list[dict] = Body(...)):
    cua_key, cua_endpoint, cua_model = await _resolve_cua()
    llm_params = ChatCompletionParam(
        model=cua_model,
        stream=False,
        temperature=0,
        max_tokens=8192,
        messages=messages,
    )

    chat_result = await chat_completions(llm_params, cua_key, cua_endpoint)

    return SmartChatResponse(data=json.loads(chat_result.body), code=200, success=True)
