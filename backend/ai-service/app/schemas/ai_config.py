from pydantic import BaseModel, Field


class AiConfigUpdate(BaseModel):
    """PUT /admin/ai-config 请求体: values 为键值对, 敏感值回传掩码时跳过不覆盖。"""

    values: dict[str, str] = Field(..., description="配置键值对")
