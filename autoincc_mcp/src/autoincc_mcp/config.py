from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GATEWAY_BASE_URL = "http://api-gateway-kong:8000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTOINCC_", case_sensitive=False, extra="ignore")

    base_url: str = Field(
        default=DEFAULT_GATEWAY_BASE_URL,
        description="Internal Kong service contract; override with AUTOINCC_BASE_URL.",
    )
    cache_url: str | None = None
    cache_ttl: int = Field(default=300, gt=0)
    timeout: float = Field(default=30, gt=0)
    retries: int = Field(default=3, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = Field(default=8080, ge=1, le=65535)
    mcp_transport: Literal["streamable-http", "sse", "stdio"] = "streamable-http"


@lru_cache
def get_config() -> Settings:
    return Settings()
