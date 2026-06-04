"""配置(读 .env)。PoC 独立,不共享主项目配置。"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TAVILY_API_KEY: str = ""
    TAVILY_API_URL: str = "https://api.tavily.com"

    QWEN_API_KEY: str = ""
    QWEN_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    CACHE_TTL_HOURS: int = 24
    CACHE_DIR: str = ".cache"

    REQUEST_TIMEOUT_SECONDS: int = 20


settings = Settings()
