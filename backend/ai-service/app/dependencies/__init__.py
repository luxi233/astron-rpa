from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.redis_op import get_redis
from app.services.point import UserPointService


def get_user_id_from_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Header(default=None, alias="user_id"),
) -> str:
    """
    从请求头中获取用户ID，优先解析 X-User-Id，如果不存在则解析 user_id。

    引擎链路(流程执行器/AI 修复等)无法携带登录态 header, 缺失时回退到
    配置的 DEFAULT_USER_ID(默认空串=不兜底, 维持 401)。
    """
    header_user_id = x_user_id or user_id

    if header_user_id is None:
        default_user_id = get_settings().DEFAULT_USER_ID
        if default_user_id:
            return default_user_id
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-Id or user_id header.",
        )
    return header_user_id


def get_user_point_service(db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)) -> UserPointService:
    return UserPointService(db, redis)
