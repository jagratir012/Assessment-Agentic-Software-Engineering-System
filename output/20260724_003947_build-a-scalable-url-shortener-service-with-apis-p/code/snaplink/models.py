"""
SnapLink Data Models
Defines SQLAlchemy ORM models for ShortURL and ApiKey entities.
Used by the Analytics Query Service and shared across Python-based services.
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class URLStatus(str, enum.Enum):
    """Lifecycle status of a shortened URL."""
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    EXPIRED = "expired"


class ValidationStatus(str, enum.Enum):
    """Reachability validation state of a shortened URL."""
    PENDING = "pending"
    VALID = "valid"
    UNREACHABLE = "unreachable"


class ShortURL(Base):
    """
    Core entity representing a shortened URL record.

    Stores the mapping between a short code (or custom alias) and the
    original long URL, along with ownership, expiration, and status metadata.
    The long_url column is encrypted at rest via pgcrypto in production.
    """
    __tablename__ = "short_urls"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Primary key, UUID v4",
    )
    short_code: str = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="7-char Base62 code or custom alias; globally unique",
    )
    long_url: str = Column(
        Text,
        nullable=False,
        comment="Original destination URL; encrypted at rest via pgcrypto",
    )
    owner_api_key_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to ApiKey; determines tenant ownership",
    )
    status: URLStatus = Column(
        Enum(URLStatus, name="url_status_enum"),
        nullable=False,
        default=URLStatus.ACTIVE,
        server_default="active",
        index=True,
        comment="Lifecycle state: active | deactivated | expired",
    )
    is_custom_alias: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when the short_code was user-supplied",
    )
    ttl_seconds: Optional[int] = Column(
        Integer,
        nullable=True,
        comment="Time-to-live in seconds; NULL means no expiry",
    )
    expires_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Computed expiry timestamp; indexed for sweep queries",
    )
    tags: Optional[List[str]] = Column(
        ARRAY(Text),
        nullable=True,
        comment="Owner-defined labels for organisation",
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last modification timestamp",
    )
    deleted_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft-delete timestamp; NULL means not deleted",
    )
    validation_status: ValidationStatus = Column(
        Enum(ValidationStatus, name="validation_status_enum"),
        nullable=False,
        default=ValidationStatus.PENDING,
        server_default="pending",
        comment="Async reachability check result",
    )

    # Relationship back to the owning API key
    owner: "ApiKey" = relationship("ApiKey", back_populates="short_urls")

    __table_args__ = (
        # Composite index for tenant-scoped listing queries
        Index("ix_short_urls_owner_status", "owner_api_key_id", "status"),
        # Partial index for expiry sweep — only rows that can expire
        Index(
            "ix_short_urls_expires_at_active",
            "expires_at",
            postgresql_where=(Column("expires_at").isnot(None)),
        ),
    )

    def __repr__(self) -> str:
        return f"<ShortURL code={self.short_code!r} status={self.status}>"

    @property
    def is_expired(self) -> bool:
        """Runtime expiry check independent of the persisted status field."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_accessible(self) -> bool:
        """True only when the URL can serve redirects."""
        return self.status == URLStatus.ACTIVE and not self.is_expired


class ApiKey(Base):
    """
    Represents a tenant API key used for authentication and rate limiting.

    Raw API keys are never stored; only the SHA-256 hash is persisted.
    The key_prefix (first 8 chars) is stored in plaintext for display.
    owner_email is encrypted at rest via pgcrypto in production.
    """
    __tablename__ = "api_keys"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    key_hash: str = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the raw API key",
    )
    key_prefix: str = Column(
        String(8),
        nullable=False,
        comment="First 8 chars of raw key for identification (e.g. snpl_abc1)",
    )
    owner_email: Optional[str] = Column(
        String(320),
        nullable=True,
        comment="Tenant contact email; encrypted at rest",
    )
    tenant_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Logical tenant grouping for multi-tenant isolation",
    )
    rate_limit_rpm: int = Column(
        Integer,
        nullable=False,
        default=1000,
        server_default="1000",
        comment="Max URL creation requests per minute",
    )
    rate_limit_rps_redirect: int = Column(
        Integer,
        nullable=False,
        default=500,
        server_default="500",
        comment="Max redirect requests per second",
    )
    is_active: bool = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    scopes: List[str] = Column(
        ARRAY(Text),
        nullable=False,
        comment="Permission scopes e.g. ['url:create','analytics:read']",
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Updated on each authenticated request",
    )
    expires_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Key expiry; NULL means never expires",
    )

    # One API key owns many short URLs
    short_urls: List[ShortURL] = relationship(
        "ShortURL", back_populates="owner", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey prefix={self.key_prefix!r} tenant={self.tenant_id}>"

    @property
    def is_valid(self) -> bool:
        """True when the key is active and not expired."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at.replace(tzinfo=None):
            return False
        return True


class ClickEvent(Base):
    """
    TimescaleDB hypertable for raw click events.

    Partitioned by time (created_at) via TimescaleDB extension.
    Raw events are purged after 90 days by the scheduled Lambda job.
    IP addresses are stored as truncated/hashed values for GDPR compliance.
    """
    __tablename__ = "click_events"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_code: str = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Denormalised short code for fast time-series queries",
    )
    short_url_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="FK to short_urls.id (not enforced as FK for TimescaleDB perf)",
    )
    tenant_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Denormalised tenant_id for isolation without joins",
    )
    # GDPR-compliant: store only the /24 subnet prefix (last octet zeroed)
    ip_prefix: Optional[str] = Column(
        String(45),
        nullable=True,
        comment="Anonymised IP: IPv4 /24 prefix or IPv6 /48 prefix",
    )
    user_agent: Optional[str] = Column(Text, nullable=True)
    referrer: Optional[str] = Column(Text, nullable=True)
    country_code: Optional[str] = Column(
        String(2),
        nullable=True,
        comment="ISO 3166-1 alpha-2 from MaxMind GeoIP2",
    )
    browser: Optional[str] = Column(String(64), nullable=True)
    os: Optional[str] = Column(String(64), nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="TimescaleDB partition key",
    )

    __table_args__ = (
        # Composite index for tenant-scoped time-series queries
        Index("ix_click_events_short_code_time", "short_code", "created_at"),
        Index("ix_click_events_tenant_time", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ClickEvent short_code={self.short_code!r} at={self.created_at}>"
