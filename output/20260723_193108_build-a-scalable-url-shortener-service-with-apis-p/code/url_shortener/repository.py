"""Data access layer — all database queries live here."""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.models import ClickEvent, ShortURL

logger = logging.getLogger(__name__)


class ShortURLRepository:
    """CRUD operations for ShortURL entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, short_url: ShortURL) -> ShortURL:
        """Persist a new ShortURL record."""
        self._session.add(short_url)
        await self._session.flush()  # Populate server-side defaults
        await self._session.refresh(short_url)
        return short_url

    async def get_by_id(self, url_id: UUID) -> Optional[ShortURL]:
        """Fetch a ShortURL by its primary key."""
        result = await self._session.execute(
            select(ShortURL).where(ShortURL.id == url_id)
        )
        return result.scalar_one_or_none()

    async def get_by_short_code(self, short_code: str) -> Optional[ShortURL]:
        """Fetch an active, non-expired ShortURL by its short code."""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(ShortURL).where(
                ShortURL.short_code == short_code,
                ShortURL.is_active.is_(True),
                (ShortURL.expires_at.is_(None)) | (ShortURL.expires_at > now),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_custom_alias(self, alias: str) -> Optional[ShortURL]:
        """Fetch an active ShortURL by its custom alias."""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(ShortURL).where(
                ShortURL.custom_alias == alias,
                ShortURL.is_active.is_(True),
                (ShortURL.expires_at.is_(None)) | (ShortURL.expires_at > now),
            )
        )
        return result.scalar_one_or_none()

    async def short_code_exists(self, short_code: str) -> bool:
        """Return True if the short code is already taken (any status)."""
        result = await self._session.execute(
            select(func.count()).where(ShortURL.short_code == short_code)
        )
        return (result.scalar() or 0) > 0

    async def alias_exists(self, alias: str) -> bool:
        """Return True if the custom alias is already taken."""
        result = await self._session.execute(
            select(func.count()).where(ShortURL.custom_alias == alias)
        )
        return (result.scalar() or 0) > 0

    async def list_urls(
        self,
        page: int = 1,
        page_size: int = 20,
        api_key: Optional[str] = None,
        include_inactive: bool = False,
    ) -> Tuple[List[ShortURL], int]:
        """Return a paginated list of ShortURLs with total count."""
        base_query = select(ShortURL)
        count_query = select(func.count()).select_from(ShortURL)

        if api_key:
            base_query = base_query.where(ShortURL.api_key == api_key)
            count_query = count_query.where(ShortURL.api_key == api_key)

        if not include_inactive:
            base_query = base_query.where(ShortURL.is_active.is_(True))
            count_query = count_query.where(ShortURL.is_active.is_(True))

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self._session.execute(
            base_query.order_by(ShortURL.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return items, total

    async def update(self, url_id: UUID, **kwargs) -> Optional[ShortURL]:
        """Update fields on a ShortURL record."""
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self._session.execute(
            update(ShortURL).where(ShortURL.id == url_id).values(**kwargs)
        )
        return await self.get_by_id(url_id)

    async def increment_click_count(self, url_id: UUID) -> None:
        """Atomically increment the click counter."""
        await self._session.execute(
            update(ShortURL)
            .where(ShortURL.id == url_id)
            .values(click_count=ShortURL.click_count + 1)
        )

    async def delete(self, url_id: UUID) -> bool:
        """Hard-delete a ShortURL and cascade to click events."""
        result = await self._session.execute(
            delete(ShortURL).where(ShortURL.id == url_id)
        )
        return result.rowcount > 0

    async def soft_delete(self, url_id: UUID) -> bool:
        """Deactivate a ShortURL without removing the record."""
        result = await self._session.execute(
            update(ShortURL)
            .where(ShortURL.id == url_id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0


class ClickEventRepository:
    """Write and query ClickEvent analytics records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, event: ClickEvent) -> ClickEvent:
        """Persist a new click event."""
        self._session.add(event)
        await self._session.flush()
        return event

    async def count_by_url(self, short_url_id: UUID) -> int:
        """Total click count for a URL."""
        result = await self._session.execute(
            select(func.count()).where(ClickEvent.short_url_id == short_url_id)
        )
        return result.scalar() or 0

    async def count_unique_ips(self, short_url_id: UUID) -> int:
        """Count of distinct IP addresses."""
        result = await self._session.execute(
            select(func.count(func.distinct(ClickEvent.ip_address))).where(
                ClickEvent.short_url_id == short_url_id
            )
        )
        return result.scalar() or 0

    async def count_since(self, short_url_id: UUID, since: datetime) -> int:
        """Click count since a given datetime."""
        result = await self._session.execute(
            select(func.count()).where(
                ClickEvent.short_url_id == short_url_id,
                ClickEvent.clicked_at >= since,
            )
        )
        return result.scalar() or 0

    async def top_values(
        self, short_url_id: UUID, column_name: str, limit: int = 10
    ) -> List[dict]:
        """Return top N values for a given column (referrer, country, etc.)."""
        col = getattr(ClickEvent, column_name)
        result = await self._session.execute(
            select(col, func.count().label("count"))
            .where(ClickEvent.short_url_id == short_url_id, col.isnot(None))
            .group_by(col)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [{"value": row[0], "count": row[1]} for row in result.all()]

    async def clicks_by_day(
        self, short_url_id: UUID, days: int = 30
    ) -> List[dict]:
        """Aggregate click counts grouped by calendar day."""
        result = await self._session.execute(
            text(
                """
                SELECT DATE(clicked_at AT TIME ZONE 'UTC') AS day,
                       COUNT(*) AS count
                FROM click_events
                WHERE short_url_id = :url_id
                  AND clicked_at >= NOW() - INTERVAL ':days days'
                GROUP BY day
                ORDER BY day ASC
                """
            ),
            {"url_id": str(short_url_id), "days": days},
        )
        return [{"date": str(row[0]), "count": row[1]} for row in result.all()]

    async def list_events(
        self,
        short_url_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ClickEvent], int]:
        """Paginated list of click events for a URL."""
        count_result = await self._session.execute(
            select(func.count()).where(ClickEvent.short_url_id == short_url_id)
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(ClickEvent)
            .where(ClickEvent.short_url_id == short_url_id)
            .order_by(ClickEvent.clicked_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        events = list(result.scalars().all())
        return events, total
