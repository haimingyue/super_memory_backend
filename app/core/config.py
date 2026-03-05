"""
应用配置管理
"""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "Super Memory API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS 配置
    CORS_ORIGINS: list[str] = ["*"]

    # 阿里云通义千问配置
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-turbo"  # 可选：qwen-turbo, qwen-plus, qwen-max

    # LangChain 配置
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048

    # 数据库配置（可选）
    DATABASE_URL: str = "sqlite:///./super_memory.db"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"release", "prod", "production"}:
                return False
            if v in {"debug", "dev", "development"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
