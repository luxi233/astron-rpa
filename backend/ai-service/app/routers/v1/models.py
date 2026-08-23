import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_user_id_from_header
from app.logger import get_logger
from app.services import ai_config

logger = get_logger(__name__)

router = APIRouter(
    prefix="/models",
    tags=["统一大模型接口"],
)


async def _resolve_models_upstream() -> tuple[str, str]:
    """每请求现读配置(热更新), 返回 (api_key, models_endpoint)。"""
    config = await ai_config.get_ai_config()
    base_url = config.get(ai_config.AICHAT_BASE_URL, "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="大模型上游未配置, 请在 AI 设置中配置 AICHAT_BASE_URL")
    return config.get(ai_config.AICHAT_API_KEY, ""), f"{base_url}/models"


@router.get("")
@router.get("/")
async def list_models(current_user_id: str = Depends(get_user_id_from_header)):
    """
    List available models.
    """
    api_key, api_endpoint = await _resolve_models_upstream()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_endpoint, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{model_id}")
async def get_model(
    model_id: str, current_user_id: str = Depends(get_user_id_from_header)
):
    """
    Get details of a specific model.
    """
    api_key, api_endpoint = await _resolve_models_upstream()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_endpoint}/{model_id}", headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
