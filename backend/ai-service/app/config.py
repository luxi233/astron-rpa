from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Service"
    API_VERSION: str = "1.0"
    DATABASE_URL: str
    DATABASE_USERNAME: str
    DATABASE_PASSWORD: str
    REDIS_URL: str

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "/app/log"

    MONTHLY_GRANT_AMOUNT: int = 100000

    AICHAT_POINTS_COST: int = 100
    OCR_GENERAL_POINTS_COST: int = 50
    JFBYM_POINTS_COST: int = 10

    # 引擎链路(桌面端流程执行器等)无登录态注入 user_id header, 缺失时回退到该默认用户计费;
    # 默认空串=不兜底(维持 401), 由部署环境按需注入启用
    DEFAULT_USER_ID: str = ""

    # AI 配置管理接口写操作令牌(纵深防御, 可选): 配置后 PUT /admin/ai-config 与
    # POST /admin/ai-config/test 须携带匹配的 X-Admin-Token header; 默认空串=不启用(向后兼容)
    AI_CONFIG_ADMIN_TOKEN: str = ""

    # 上游服务配置: 默认空串, 生产由 docker env 注入, 亦可在运行时经
    # /admin/ai-config 管理接口落库覆盖(见 services/ai_config.py, 支持热更新)
    AICHAT_BASE_URL: str = ""
    AICHAT_API_KEY: str = ""

    CUA_BASE_URL: str = ""
    CUA_API_KEY: str = ""

    XFYUN_APP_ID: str = ""
    XFYUN_API_SECRET: str = ""
    XFYUN_API_KEY: str = ""

    JFBYM_ENDPOINT: str = "http://api.jfbym.com/api/YmServer/customApi"
    JFBYM_API_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
