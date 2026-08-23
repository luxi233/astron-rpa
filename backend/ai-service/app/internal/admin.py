import httpx
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import get_settings
from app.dependencies import get_user_point_service
from app.schemas import ResCode, StandardResponse
from app.schemas.ai_config import AiConfigUpdate
from app.services import ai_config
from app.services.point import PointTransactionType, UserPointService

router = APIRouter()


async def require_admin_token(x_admin_token: str | None = Header(default=None)):
    """可选管理令牌(纵深防御): 配置 AI_CONFIG_ADMIN_TOKEN 后, 写操作须携带匹配的 X-Admin-Token。

    默认空串=不启用(向后兼容, 依赖网关认证的既有信任模型)。
    """
    expected = get_settings().AI_CONFIG_ADMIN_TOKEN
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=403, detail="admin token required")


@router.post("")
async def update_admin():
    return {"message": "Admin getting schwifty"}


@router.get("/ai-config")
async def read_ai_config():
    """读取当前生效的 AI 配置(敏感值掩码返回)。"""
    config = await ai_config.get_ai_config()
    masked = {key: ai_config.mask_value(key, value) for key, value in config.items()}
    return StandardResponse(code=ResCode.SUCCESS, msg="", data=masked)


@router.put("/ai-config", dependencies=[Depends(require_admin_token)])
async def update_ai_config(payload: AiConfigUpdate):
    """保存 AI 配置, TTL 内对全部 worker 生效(无需重启)。

    掩码值(含***)视为未修改跳过; 空串落库 = 清除该键的 DB 覆盖(回落环境变量默认)。
    """
    try:
        saved = await ai_config.set_ai_config(payload.values)
    except ValueError as e:
        # 非法 BASE_URL(非 http/https scheme)拒绝落库, msg 由前端 toast 展示
        return StandardResponse(code=ResCode.ERR, msg=str(e), data={"saved_keys": []})
    return StandardResponse(
        code=ResCode.SUCCESS,
        msg="已保存, 即时生效",
        data={"saved_keys": sorted(saved.keys())},
    )


@router.post("/ai-config/test", dependencies=[Depends(require_admin_token)])
async def test_ai_config():
    """用当前生效配置向上游发一次最小 chat 请求验证连通性。"""
    config = await ai_config.get_ai_config()
    api_key, endpoint = await ai_config.resolve_llm()
    if not endpoint:
        return StandardResponse(
            code=ResCode.SUCCESS,
            msg="",
            data={"ok": False, "message": "未配置大模型上游(AICHAT_BASE_URL)"},
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": config.get(ai_config.DEFAULT_MODEL),
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "stream": False,
                },
            )
            response.raise_for_status()
        return StandardResponse(
            code=ResCode.SUCCESS,
            msg="",
            data={"ok": True, "message": "连接成功"},
        )
    except httpx.HTTPStatusError as e:
        return StandardResponse(
            code=ResCode.SUCCESS,
            msg="",
            data={"ok": False, "message": f"上游返回 {e.response.status_code}: {e.response.text[:200]}"},
        )
    except Exception as e:
        return StandardResponse(
            code=ResCode.SUCCESS,
            msg="",
            data={"ok": False, "message": f"连接失败: {e}"},
        )


@router.get("/user/points")
async def get_user_points(
    user_id: str,
    user_point_service: UserPointService = Depends(get_user_point_service),
):
    user_point = await user_point_service.get_cached_points(user_id)
    return {"user_point": user_point}


@router.post("/user/points")
async def add_user_points(
    user_id: str,
    amount: int,
    user_point_service: UserPointService = Depends(get_user_point_service),
):
    """
    Add points to a user.
    """
    user_point = await user_point_service.manual_add_points(
        user_id=user_id,
        amount=amount,
    )
    return {
        "message": f"Added {amount} points to user {user_id}",
        "user_point": user_point,
    }


@router.post("/user/points/deduct")
async def deduct_user_points(
    user_id: str,
    amount: int,
    user_point_service: UserPointService = Depends(get_user_point_service),
):
    """
    Deduct points from a user.
    """
    user_point = await user_point_service.deduct_points(
        user_id=user_id,
        amount=amount,
        transaction_type=PointTransactionType.MANUAL_DEDUCT,
    )
    return {
        "message": f"Deducted {amount} points from user {user_id}",
        "user_point": user_point,
    }
