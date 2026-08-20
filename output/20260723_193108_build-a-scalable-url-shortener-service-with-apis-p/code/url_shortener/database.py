"""Async database engine, session factory, and Redis connection pool."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from url_shortener.config import get_settings
from url_shortener.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# PostgreSQL async engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,          # Verify connections before use
    echo=settings.debug,         # Log SQL in debug mode
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # Avoid lazy-load issues after commit
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised")


async def close_db() -> None:
    """Dispose the engine connection pool gracefully."""
    await engine.dispose()
    logger.info("Database connection pool closed")


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Redis connection pool
# ---------------------------------------------------------------------------

_redis_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    """Initialise the Redis connection pool."""
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    # Verify connectivity
    await _redis_pool.ping()
    logger.info("Redis connection pool initialised")


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
    logger.info("Redis connection pool closed")


def get_redis() -> aioredis.Redis:
    """Return the shared Redis client (raises if not initialised)."""
    if _redis_pool is None:
        raise RuntimeError("Redis pool is not initialised. Call init_redis() first.")
    return _redis_pool
