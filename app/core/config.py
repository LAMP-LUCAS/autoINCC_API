"""Application configuration management using Pydantic Settings V2.

Loads environment variables from `.env` file or process environment.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration class for AutoINCC application.

    Attributes:
        APP_ENV (str): Runtime environment (development, staging, production).
        APP_NAME (str): Name of the application.
        APP_VERSION (str): Application semantic version.
        DEBUG (bool): Debug mode flag.
        HOST (str): Host IP to bind server.
        PORT (int): Port number to bind server.
        API_KEY (str): Secret API key for administrative endpoints.
        DATABASE_URL (str): PostgreSQL connection URI.
        REDIS_URL (str): Redis URI for Celery broker, results, and L2 cache.
        CACHE_ENABLED (bool): Flag to enable/disable API caching in Redis.
        CACHE_TTL_SECONDS (int): Default Time-to-Live for cached endpoints.
        ETL_REQUEST_DELAY_BASE (float): Base wait time between external requests.
        ETL_REQUEST_DELAY_JITTER (float): Stochastic jitter range added to base delay.
        ETL_POLITE_PACING_ENABLED (bool): Flag to enable human-like request pacing.
        BCB_API_URL (str): Base URL for Central Bank of Brazil SGS API.
        LOG_LEVEL (str): Log verbosity level.
        API_V1_STR (str): Base prefix path for v1 API endpoints.
    """

    APP_ENV: str = "development"
    APP_NAME: str = "AutoINCC API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_KEY: str = "autoincc_secret_token_dev_123"
    DATABASE_URL: str = "postgresql://postgres:postgrespassword@localhost:5432/autoincc"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    ETL_REQUEST_DELAY_BASE: float = 1.5
    ETL_REQUEST_DELAY_JITTER: float = 1.5
    ETL_POLITE_PACING_ENABLED: bool = True
    BCB_API_URL: str = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
