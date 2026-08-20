"""SQLAlchemy ORM models and Pydantic schemas for the URL shortener service."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class ShortURL(Base):
    """Represents a shortened URL record in the database."""

    __tablename__ = "short_urls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_code = Column(String(64), unique=True, nullable=False, index=True)
    original_url = Column(Text, nullable=False)
    custom_alias = Column(String(64), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    click_count = Column(BigInteger, default=0, nullable=False)
    creator_ip = Column(String(45), nullable=True)  # IPv6 max length
    api_key = Column(String(128), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Relationship to analytics events
    analytics = relationship(
        "ClickEvent", back_populates="short_url", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_short_urls_short_code_active", "short_code", "is_active"),
        Index("ix_short_urls_expires_at", "expires_at"),
        Index("ix_short_urls_api_key", "api_key"),
    )

    def __repr__(self) -> str:
        return f"<ShortURL id={self.id} code={self.short_code}>"


class ClickEvent(Base):
    """Represents a single click/redirect event for analytics."""

    __tablename__ = "click_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_url_id = Column(
        UUID(as_uuid=True),
        ForeignKey("short_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clicked_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    country = Column(String(2), nullable=True)   # ISO 3166-1 alpha-2
    city = Column(String(128), nullable=True)
    device_type = Column(String(32), nullable=True)  # mobile, desktop, tablet, bot
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)

    short_url = relationship("ShortURL", back_populates="analytics")

    __table_args__ = (
        Index("ix_click_events_short_url_clicked", "short_url_id", "clicked_at"),
    )

    def __repr__(self) -> str:
        return f"<ClickEvent id={self.id} url_id={self.short_url_id}>"


# ---------------------------------------------------------------------------
# Pydantic Request / Response Schemas
# ---------------------------------------------------------------------------


class URLCreateRequest(BaseModel):
    """Request body for creating a shortened URL."""

    original_url: AnyHttpUrl = Field(..., description="The long URL to shorten")
    custom_alias: Optional[str] = Field(
        None,
        description="Optional vanity alias (3-50 alphanumeric/hyphen chars)",
        min_length=3,
        max_length=50,
    )
    ttl_days: Optional[int] = Field(
        None,
        description="Time-to-live in days (0 = never expires)",
        ge=0,
        le=3650,
    )
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        """Ensure alias contains only safe characters."""
        if v is None:
            return v
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Custom alias may only contain letters, digits, hyphens, and underscores"
            )
        return v.lower()


class URLUpdateRequest(BaseModel):
    """Request body for updating an existing shortened URL."""

    original_url: Optional[AnyHttpUrl] = None
    is_active: Optional[bool] = None
    ttl_days: Optional[int] = Field(None, ge=0, le=3650)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class URLResponse(BaseModel):
    """Response schema for a shortened URL."""

    id: uuid.UUID
    short_code: str
    short_url: str
    original_url: str
    custom_alias: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int
    title: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ClickEventResponse(BaseModel):
    """Response schema for a single click event."""

    id: uuid.UUID
    clicked_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None

    model_config = {"from_attributes": True}


class AnalyticsSummary(BaseModel):
    """Aggregated analytics summary for a short URL."""

    short_code: str
    total_clicks: int
    unique_ips: int
    clicks_last_24h: int
    clicks_last_7d: int
    clicks_last_30d: int
    top_referrers: List[dict]
    top_countries: List[dict]
    top_browsers: List[dict]
    top_devices: List[dict]
    clicks_by_day: List[dict]


class AnalyticsDetailResponse(BaseModel):
    """Full analytics response including summary and recent events."""

    summary: AnalyticsSummary
    recent_events: List[ClickEventResponse]
    page: int
    page_size: int
    total_events: int


class URLListResponse(BaseModel):
    """Paginated list of shortened URLs."""

    items: List[URLResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    cache: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
