"""
SnapLink Configuration
Centralised settings management using Pydantic BaseSettings.
All secrets are injected via environment variables; no hardcoded credentials.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyUrl, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Pydantic validates types and raises on startup if required vars are missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = Field(default="SnapLink", description="Service display name")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(
        default="production",
        description="One of: development | staging | production",
    )
    debug: bool = Field(default=False, description="Enable debug logging")
    log_level: str = Field(default="INFO")

    # Base URL used to construct full short URLs in API responses
    base_url: str = Field(
        default="https://snpl.ink",
        description="Public-facing base URL for short links",
    )

    # -------------------------------------------------------------------------
    # PostgreSQL (Aurora PostgreSQL 15 via PgBouncer)
    # -------------------------------------------------------------------------
    database_url: PostgresDsn = Field(
        ...,
        description="Async PostgreSQL DSN (asyncpg driver) via PgBouncer",
        examples=["postgresql+asyncpg://user:pass@pgbouncer:5432/snaplink"],
    )
    database_pool_size: int = Field(default=20, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout: int = Field(default=30, ge=5)
    database_pool_recycle: int = Field(
        default=1800,
        description="Recycle connections every 30 min to avoid stale connections",
    )

    # Read replica DSN for analytics queries (Aurora reader endpoint)
    database_read_url: Optional[PostgresDsn] = Field(
        default=None,
        description="Read-only replica DSN for analytics queries",
    )

    # -------------------------------------------------------------------------
    # TimescaleDB (click events time-series)
    # -------------------------------------------------------------------------
    timescale_url: Optional[PostgresDsn] = Field(
        default=None,
        description="TimescaleDB DSN for click event storage and queries",
    )

    # -------------------------------------------------------------------------
    # Redis (ElastiCache 7.x cluster mode)
    # -------------------------------------------------------------------------
    redis_url: RedisDsn = Field(
        ...,
        description="Redis DSN for cache, rate limiting, and Celery broker",
        examples=["rediss://user:pass@cluster.cache.amazonaws.com:6380/0"],
    )
    redis_max_connections: int = Field(default=50, ge=5)
    redis_socket_timeout: float = Field(default=0.5, description="Seconds")
    redis_socket_connect_timeout: float = Field(default=1.0, description="Seconds")

    # TTL for cached URL records in Redis (seconds)
    redis_url_cache_ttl: int = Field(
        default=3600,
        description="Default TTL for short_code->URL cache entries (1 hour)",
    )
    # TTL for analytics summary cache
    redis_analytics_cache_ttl: int = Field(
        default=60,
        description="TTL for cached analytics summaries (60 seconds)",
    )

    # -------------------------------------------------------------------------
    # Kafka (Amazon MSK)
    # -------------------------------------------------------------------------
    kafka_bootstrap_servers: str = Field(
        ...,
        description="Comma-separated Kafka broker addresses",
        examples=["b-1.msk.amazonaws.com:9092,b-2.msk.amazonaws.com:9092"],
    )
    kafka_click_events_topic: str = Field(
        default="snaplink.click-events",
        description="Topic for raw click events from Redirect Service",
    )
    kafka_security_protocol: str = Field(default="SASL_SSL")
    kafka_sasl_mechanism: str = Field(default="AWS_MSK_IAM")
    kafka_producer_acks: str = Field(
        default="1",
        description="Producer ack level: 0=none, 1=leader, all=full ISR",
    )
    kafka_producer_linger_ms: int = Field(
        default=5,
        description="Batch linger time for producer throughput optimisation",
    )

    # -------------------------------------------------------------------------
    # URL Shortener
    # -------------------------------------------------------------------------
    short_code_length: int = Field(
        default=7,
        description="Length of generated Base62 short codes",
    )
    max_collision_retries: int = Field(
        default=3,
        description="Max Base62 counter retries before falling back to random entropy",
    )
    url_reachability_timeout: float = Field(
        default=3.0,
        description="HTTP HEAD request timeout for URL validation (seconds)",
    )
    max_batch_size: int = Field(
        default=100,
        description="Maximum URLs per batch creation request",
    )
    max_custom_alias_length: int = Field(default=50)
    min_custom_alias_length: int = Field(default=3)

    # Redis key for the distributed counter used in Base62 generation
    redis_counter_key: str = Field(default="snaplink:global:url_counter")

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    default_rate_limit_rpm: int = Field(
        default=1000,
        description="Default URL creation rate limit (requests per minute)",
    )
    default_rate_limit_rps_redirect: int = Field(
        default=500,
        description="Default redirect rate limit (requests per second)",
    )

    # -------------------------------------------------------------------------
    # Celery / Background Workers
    # -------------------------------------------------------------------------
    celery_broker_url: Optional[str] = Field(
        default=None,
        description="Celery broker URL; defaults to redis_url if not set",
    )
    celery_result_backend: Optional[str] = Field(
        default=None,
        description="Celery result backend; defaults to redis_url if not set",
    )
    celery_task_serializer: str = Field(default="json")
    celery_result_serializer: str = Field(default="json")
    celery_task_acks_late: bool = Field(
        default=True,
        description="Acknowledge tasks only after completion for at-least-once delivery",
    )
    celery_worker_prefetch_multiplier: int = Field(default=1)

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    api_key_prefix: str = Field(
        default="snpl_",
        description="Prefix for all generated API keys",
    )
    # CORS allowed origins for the analytics API
    cors_allowed_origins: List[str] = Field(
        default=["https://app.snpl.ink"],
        description="Allowed CORS origins",
    )

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    sentry_dsn: Optional[str] = Field(default=None)
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None,
        description="OpenTelemetry collector endpoint for distributed tracing",
    )
    metrics_port: int = Field(
        default=9090,
        description="Prometheus metrics exposition port",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper

    @property
    def effective_celery_broker(self) -> str:
        """Celery broker falls back to the main Redis URL."""
        return self.celery_broker_url or str(self.redis_url)

    @property
    def effective_celery_backend(self) -> str:
        """Celery result backend falls back to the main Redis URL."""
        return self.celery_result_backend or str(self.redis_url)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.
    The lru_cache ensures settings are parsed only once per process lifetime.
    Use dependency injection in FastAPI via Depends(get_settings).
    """
    return Settings()
