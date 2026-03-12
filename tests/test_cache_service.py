"""Tests for cache service."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.services.cache_service import get_cached_summary, update_cache


@pytest.mark.asyncio
async def test_cache_hit_fresh(db_session: AsyncSession) -> None:
    """Fresh cached summary is returned."""
    b = Bookmark(
        url="https://example.com/cached",
        title="Cached",
        status=BookmarkStatus.UNREVIEWED,
    )
    db_session.add(b)
    await db_session.commit()

    await update_cache(db_session, b.url, "A summary", ["point 1", "point 2"])
    await db_session.commit()

    result = await get_cached_summary(db_session, b.url)
    assert result is not None
    summary, key_points = result
    assert summary == "A summary"
    assert key_points == ["point 1", "point 2"]


@pytest.mark.asyncio
async def test_cache_miss_expired(db_session: AsyncSession) -> None:
    """Expired cache returns None."""
    b = Bookmark(
        url="https://example.com/expired",
        title="Expired",
        status=BookmarkStatus.UNREVIEWED,
        cached_summary="Old summary",
        cached_key_points='["old point"]',
        cached_at=datetime.now(UTC) - timedelta(days=31),
    )
    db_session.add(b)
    await db_session.commit()

    result = await get_cached_summary(db_session, b.url)
    assert result is None


@pytest.mark.asyncio
async def test_cache_miss_no_bookmark(db_session: AsyncSession) -> None:
    """Cache miss when URL doesn't exist in DB."""
    result = await get_cached_summary(db_session, "https://nonexistent.com")
    assert result is None
