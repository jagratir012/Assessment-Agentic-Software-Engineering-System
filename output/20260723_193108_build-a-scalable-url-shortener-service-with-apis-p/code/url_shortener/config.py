"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "URL Shortener Service"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    base_url: str = Field(default="http://localhost:8000", env="BASE_URL")
    environment: str = Field(default="production", env="ENVIRONMENT")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/url_shortener",
        env="DATABASE_URL",
    )
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_ttl_seconds: int = Field(default=3600, env="REDIS_TTL_SECONDS")

    # Short code generation
    short_code_length: int = Field(default=7, env="SHORT_CODE_LENGTH")
    max_custom_alias_length: int = Field(default=50, env="MAX_CUSTOM_ALIAS_LENGTH")
    min_custom_alias_length: int = Field(default=3, env="MIN_CUSTOM_ALIAS_LENGTH")

    # URL validation
    url_reachability_check: bool = Field(default=True, env="URL_REACHABILITY_CHECK")
    url_check_timeout_seconds: int = Field(default=5, env="URL_CHECK_TIMEOUT_SECONDS")

    # Rate limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, env="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_burst: int = Field(default=20, env="RATE_LIMIT_BURST")

    # Default TTL for shortened URLs (0 = no expiration)
    default_url_ttl_days: int = Field(default=0, env="DEFAULT_URL_TTL_DAYS")
    max_url_ttl_days: int = Field(default=3650, env="MAX_URL_TTL_DAYS")  # 10 years

    # Analytics
    analytics_batch_size: int = Field(default=100, env="ANALYTICS_BATCH_SIZE")
    analytics_retention_days: int = Field(default=365, env="ANALYTICS_RETENTION_DAYS")

    # Security
    api_key_header: str = "X-API-Key"
    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
