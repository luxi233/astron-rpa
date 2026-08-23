from sqlalchemy import Column, DateTime, String, func

from app.database import Base


class AIConfig(Base):
    """AI 配置项(key-value), 经管理接口写入后在 TTL 内对全部 worker 生效。

    覆盖优先级: 本表 > 环境变量(见 services/ai_config.py 的合并逻辑)。
    """

    __tablename__ = "ai_configs"

    config_key = Column(String(64), primary_key=True)
    config_value = Column(String(2048), nullable=False, default="")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
