"""
Data models for the Distributed LRU Cache Layer.
Defines Pydantic models for cache entries, namespace configuration,
metrics snapshots, and API request/response schemas.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EvictionPolicy(str, Enum):
    """Supported eviction policies for L1 cache."""
    LRU = "LRU"
    LFU = "LFU"
    EXPIRE_ONLY = "EXPIRE_ONLY"


class CircuitBreakerState(str, Enum):
    """Possible states of the Redis circuit breaker."""
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Redis unavailable, using L1 only
    HALF_OPEN = "HALF_OPEN" # Probing Redis availability


class CacheTier(str, Enum):
    """Which cache tier served a hit."""
    L1 = "L1"
    L2 = "L2"
    ORIGIN = "ORIGIN"
    MISS = "MISS"


class BulkInvalidationMode(str, Enum):
    """Mode for bulk invalidation operations."""
    TAG = "TAG"
    PREFIX = "PREFIX"
    KEY_LIST = "KEY_LIST"


# ---------------------------------------------------------------------------
# Core Domain Models
# ---------------------------------------------------------------------------

class CacheEntry(BaseModel):
    """
    Represents a single cached item stored in L1 and/or L2.
    Tracks provenance, TTL, PII classification, and versioning.
    """
    key: str = Field(
        ...,
        max_length=512,
        description="Cache key — URL-safe characters only, max 512 bytes",
        pattern=r"^[\w\-\.~:@!$&'()*+,;=%]+$",
    )
    namespace: str = Field(
        ...,
        max_length=64,
        description="Namespace for isolation and config lookup",
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    value: bytes = Field(
        ...,
        description="Serialized cached value (max 1 MB by default)",
    )
    created_at: int = Field(
        default_factory=lambda: int(time.time() * 1000),
        description="Creation timestamp in epoch milliseconds",
    )
    last_accessed_at: int = Field(
        default_factory=lambda: int(time.time() * 1000),
        description="Last access timestamp (L1 in-memory only)",
    )
    expires_at: Optional[int] = Field(
        default=None,
        description="Expiry timestamp in epoch milliseconds; null = no TTL",
    )
    ttl_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Original TTL in milliseconds for reference",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for bulk invalidation grouping",
    )
    is_pii: bool = Field(
        default=False,
        description="If true, entry is excluded from L2 Redis",
    )
    size_bytes: int = Field(
        default=0,
        ge=0,
        description="Serialized value size for memory accounting",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Optimistic concurrency version for L2 updates",
    )

    @field_validator("value")
    @classmethod
    def validate_value_size(cls, v: bytes) -> bytes:
        max_size = 1_048_576  # 1 MB default; overridden per namespace
        if len(v) > max_size:
            raise ValueError(f"Value size {len(v)} exceeds max {max_size} bytes")
        return v

    @model_validator(mode="after")
    def compute_size_and_expiry(self) -> "CacheEntry":
        """Auto-compute size_bytes and expires_at from ttl_ms."""
        if self.size_bytes == 0:
            self.size_bytes = len(self.value)
        if self.ttl_ms is not None and self.expires_at is None:
            self.expires_at = self.created_at + self.ttl_ms
        return self

    def is_expired(self) -> bool:
        """Check whether this entry has passed its TTL."""
        if self.expires_at is None:
            return False
        return int(time.time() * 1000) >= self.expires_at

    def remaining_ttl_ms(self) -> Optional[int]:
        """Return remaining TTL in milliseconds, or None if no TTL."""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - int(time.time() * 1000)
        return max(0, remaining)

    model_config = {"arbitrary_types_allowed": True}


class CacheNamespaceConfig(BaseModel):
    """
    Per-namespace cache configuration controlling capacity, TTL,
    eviction policy, circuit breaker thresholds, and PII handling.
    """
    namespace: str = Field(
        ...,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Namespace identifier — primary key",
    )
    max_capacity: int = Field(
        ...,
        ge=1,
        le=1_000_000,
        description="Maximum number of entries in L1 cache",
    )
    default_ttl_ms: int = Field(
        ...,
        ge=0,
        description="Default TTL in milliseconds (0 = no expiry)",
    )
    max_entry_size_bytes: int = Field(
        default=1_048_576,
        ge=1,
        description="Maximum serialized value size per entry (default 1 MB)",
    )
    l2_enabled: bool = Field(
        default=True,
        description="Enable L2 Redis tier; set false for PII or local-only namespaces",
    )
    eviction_policy: EvictionPolicy = Field(
        default=EvictionPolicy.LRU,
        description="Eviction policy for L1 cache",
    )
    circuit_breaker_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Failure rate (0.0–1.0) to open the circuit breaker",
    )
    circuit_breaker_wait_ms: int = Field(
        default=10_000,
        ge=100,
        description="Time in OPEN state before transitioning to HALF_OPEN (ms)",
    )
    warm_up_manifest_ref: Optional[str] = Field(
        default=None,
        description="S3 URI or ConfigMap key for warm-up key manifest",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO8601 creation timestamp",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="ISO8601 last-update timestamp",
    )


class CacheMetricsSnapshot(BaseModel):
    """
    Point-in-time metrics snapshot for a single namespace on one instance.
    Exported to Prometheus and returned by the /metrics endpoint.
    """
    namespace: str
    instance_id: str = Field(description="Pod/container ID for per-instance L1 metrics")
    snapshot_at: int = Field(
        default_factory=lambda: int(time.time() * 1000),
        description="Snapshot timestamp in epoch milliseconds",
    )
    l1_size: int = Field(default=0, ge=0)
    l1_hit_count: int = Field(default=0, ge=0)
    l1_miss_count: int = Field(default=0, ge=0)
    l2_hit_count: int = Field(default=0, ge=0)
    l2_miss_count: int = Field(default=0, ge=0)
    eviction_count: int = Field(default=0, ge=0, description="LRU evictions")
    ttl_expiry_count: int = Field(default=0, ge=0, description="TTL-based expirations")
    invalidation_count: int = Field(default=0, ge=0, description="Explicit invalidations")
    get_latency_histogram: Dict[str, int] = Field(
        default_factory=dict,
        description="Prometheus histogram: bucket_ms -> count",
    )
    put_latency_histogram: Dict[str, int] = Field(
        default_factory=dict,
        description="Prometheus histogram: bucket_ms -> count",
    )
    circuit_breaker_state: CircuitBreakerState = Field(
        default=CircuitBreakerState.CLOSED,
    )
    circuit_breaker_open_count: int = Field(
        default=0,
        ge=0,
        description="Number of times circuit has opened",
    )

    @property
    def l1_hit_rate(self) -> float:
        total = self.l1_hit_count + self.l1_miss_count
        return self.l1_hit_count / total if total > 0 else 0.0

    @property
    def l2_hit_rate(self) -> float:
        total = self.l2_hit_count + self.l2_miss_count
        return self.l2_hit_count / total if total > 0 else 0.0

    @property
    def overall_hit_rate(self) -> float:
        hits = self.l1_hit_count + self.l2_hit_count
        total = hits + self.l2_miss_count  # L2 miss = full miss
        return hits / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------

class PutCacheRequest(BaseModel):
    """Request body for PUT /api/v1/cache/{namespace}/{key}."""
    value: str = Field(
        ...,
        description="Base64-encoded value to cache",
    )
    ttl_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Per-entry TTL override in milliseconds",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for bulk invalidation",
    )
    is_pii: bool = Field(
        default=False,
        description="Mark entry as PII to exclude from L2",
    )


class GetCacheResponse(BaseModel):
    """Response body for GET /api/v1/cache/{namespace}/{key}."""
    hit: bool
    tier: CacheTier
    key: str
    namespace: str
    value: Optional[str] = Field(default=None, description="Base64-encoded value")
    remaining_ttl_ms: Optional[int] = None
    is_stale: bool = False
    version: Optional[int] = None
    message: Optional[str] = None


class PutCacheResponse(BaseModel):
    """Response body for PUT /api/v1/cache/{namespace}/{key}."""
    key: str
    namespace: str
    effective_ttl_ms: Optional[int]
    tiers_written: List[str]
    eviction_occurred: bool
    version: int


class DeleteCacheResponse(BaseModel):
    """Response body for DELETE /api/v1/cache/{namespace}/{key}."""
    key: str
    namespace: str
    tiers_invalidated: List[str]
    invalidation_broadcast: bool


class BulkInvalidateRequest(BaseModel):
    """Request body for POST /api/v1/cache/{namespace}/invalidate/bulk."""
    mode: BulkInvalidationMode
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags to match for TAG mode",
    )
    prefix: Optional[str] = Field(
        default=None,
        description="Key prefix pattern for PREFIX mode",
    )
    keys: Optional[List[str]] = Field(
        default=None,
        description="Explicit key list for KEY_LIST mode",
    )

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "BulkInvalidateRequest":
        if self.mode == BulkInvalidationMode.TAG and not self.tags:
            raise ValueError("'tags' required for TAG mode")
        if self.mode == BulkInvalidationMode.PREFIX and not self.prefix:
            raise ValueError("'prefix' required for PREFIX mode")
        if self.mode == BulkInvalidationMode.KEY_LIST and not self.keys:
            raise ValueError("'keys' required for KEY_LIST mode")
        return self


class BulkInvalidateResponse(BaseModel):
    """Response body for POST /api/v1/cache/{namespace}/invalidate/bulk."""
    namespace: str
    keys_invalidated: int
    l1_invalidated: int
    l2_invalidated: int
    broadcast_sent: bool


class WarmUpRequest(BaseModel):
    """Request body for POST /api/v1/cache/{namespace}/warm."""
    keys: Optional[List[str]] = Field(
        default=None,
        description="Explicit keys to preload",
    )
    manifest_ref: Optional[str] = Field(
        default=None,
        description="S3 URI or ConfigMap key for warm-up manifest",
    )


class WarmUpResponse(BaseModel):
    """Response body for POST /api/v1/cache/{namespace}/warm."""
    job_id: str
    namespace: str
    status: str
    keys_scheduled: int
