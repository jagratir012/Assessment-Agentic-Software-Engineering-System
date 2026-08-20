"""
Configuration management for the Distributed LRU Cache Layer.
Loads settings from environment variables with sensible defaults.
Supports hot-reload via a background watcher thread.
"""

from __future__ import annotations

import logging
import os
import socket
from functools import lru_cache
from typing import Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from distributed_lru_cache.models import CacheNamespaceConfig, EvictionPolicy

logger = logging.getLogger(__name__)


class RedisSettings(BaseSettings):
    """Redis cluster connection settings."""

    # Comma-separated list of host:port for cluster nodes
    redis_cluster_nodes: str = Field(
        default="localhost:7000,localhost:7001,localhost:7002",
        description="Comma-separated Redis cluster node addresses",
    )
    redis_password: Optional[str] = Field(default=None)
    redis_ssl: bool = Field(default=False)
    redis_socket_timeout: float = Field(default=0.5, ge=0.01)
    redis_socket_connect_timeout: float = Field(default=1.0, ge=0.01)
    redis_max_connections: int = Field(default=50, ge=1)
    redis_decode_responses: bool = Field(default=False)  # We handle bytes
    redis_retry_on_timeout: bool = Field(default=True)
    redis_health_check_interval: int = Field(default=30, ge=5)

    @property
    def startup_nodes(self) -> List[Dict[str, str]]:
        """Parse cluster node list into dicts for redis-py ClusterClient."""
        nodes = []
        for node in self.redis_cluster_nodes.split(","):
            node = node.strip()
            if ":" in node:
                host, port = node.rsplit(":", 1)
                nodes.append({"host": host.strip(), "port": port.strip()})
            else:
                nodes.append({"host": node, "port": "6379"})
        return nodes

    model_config = {"env_prefix": "", "case_sensitive": False}


class ObservabilitySettings(BaseSettings):
    """Prometheus and OpenTelemetry configuration."""

    otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OpenTelemetry Collector OTLP gRPC endpoint",
    )
    otlp_enabled: bool = Field(default=True)
    metrics_prefix: str = Field(
        default="cache",
        description="Prometheus metric name prefix",
    )
    # Histogram buckets in milliseconds
    latency_buckets_ms: str = Field(
        default="0.1,0.5,1,2,5,10,25,50,100,250,500,1000",
    )

    @property
    def latency_buckets(self) -> List[float]:
        return [float(b) for b in self.latency_buckets_ms.split(",")]

    model_config = {"env_prefix": "", "case_sensitive": False}


class AppSettings(BaseSettings):
    """Top-level application settings."""

    app_name: str = Field(default="distributed-lru-cache")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="production")
    log_level: str = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=4, ge=1)

    # Instance identity (auto-detected from hostname / K8s downward API)
    instance_id: str = Field(
        default_factory=lambda: os.environ.get(
            "POD_NAME", socket.gethostname()
        )
    )

    # Pub/Sub invalidation channel prefix
    invalidation_channel_prefix: str = Field(
        default="cache:invalidate",
        description="Redis Pub/Sub channel prefix for L1 invalidation events",
    )

    # Default namespace config (used when no explicit config is registered)
    default_max_capacity: int = Field(default=10_000, ge=1)
    default_ttl_ms: int = Field(default=300_000, ge=0)  # 5 minutes
    default_l2_enabled: bool = Field(default=True)
    default_eviction_policy: EvictionPolicy = Field(default=EvictionPolicy.LRU)
    default_circuit_breaker_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    default_circuit_breaker_wait_ms: int = Field(default=10_000, ge=100)

    # Warm-up settings
    warm_up_concurrency: int = Field(
        default=10,
        ge=1,
        description="Number of concurrent warm-up fetch coroutines",
    )
    warm_up_timeout_ms: int = Field(
        default=30_000,
        ge=1000,
        description="Total warm-up timeout in milliseconds",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    model_config = {"env_prefix": "", "case_sensitive": False}


class Settings(BaseSettings):
    """Aggregated settings object injected throughout the application."""

    app: AppSettings = Field(default_factory=AppSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    observability: ObservabilitySettings = Field(
        default_factory=ObservabilitySettings
    )

    # In-memory namespace config registry (populated at startup or via API)
    _namespace_configs: Dict[str, CacheNamespaceConfig] = {}

    def get_namespace_config(self, namespace: str) -> CacheNamespaceConfig:
        """Return namespace config or a default if not explicitly registered."""
        if namespace in self._namespace_configs:
            return self._namespace_configs[namespace]
        # Return a default config derived from app-level defaults
        return CacheNamespaceConfig(
            namespace=namespace,
            max_capacity=self.app.default_max_capacity,
            default_ttl_ms=self.app.default_ttl_ms,
            l2_enabled=self.app.default_l2_enabled,
            eviction_policy=self.app.default_eviction_policy,
            circuit_breaker_threshold=self.app.default_circuit_breaker_threshold,
            circuit_breaker_wait_ms=self.app.default_circuit_breaker_wait_ms,
        )

    def register_namespace(self, config: CacheNamespaceConfig) -> None:
        """Register or update a namespace configuration."""
        self._namespace_configs[config.namespace] = config
        logger.info("Registered namespace config: %s", config.namespace)

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.
    Cached after first call; call get_settings.cache_clear() to hot-reload.
    """
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.app.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info(
        "Settings loaded — instance_id=%s env=%s",
        settings.app.instance_id,
        settings.app.environment,
    )
    return settings
