"""Cache and reuse summaries to avoid redundant fetches and LLM calls."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark


# Consider cache stale after this many days
CACHE_TTL_DAYS = 30


def _is_cache_fresh(cached_at: datetime | None) -> bool:
    if not cached_at:
        return False
    cutoff = datetime.now(UTC) - timedelta(days=CACHE_TTL_DAYS)
    dt = cached_at.replace(tzinfo=UTC) if cached_at.tzinfo is None else cached_at
    return bool(dt >= cutoff)


async def get_cached_summary(session: AsyncSession, url: str) -> tuple[str, list[str]] | None:
    """Return (summary, key_points) if cache exists and is fresh, else None."""
    result = await session.execute(select(Bookmark).where(Bookmark.url == url))
    b = result.scalar_one_or_none()
    if not b or not b.cached_summary or not _is_cache_fresh(b.cached_at):
        return None
    import json

    pts: list[str] = json.loads(b.cached_key_points) if b.cached_key_points else []
    return (b.cached_summary, pts)


async def update_cache(
    session: AsyncSession,
    url: str,
    summary: str,
    key_points: list[str],
) -> None:
    """Update bookmark cache for the given URL."""
    result = await session.execute(select(Bookmark).where(Bookmark.url == url))
    b = result.scalar_one_or_none()
    if b:
        import json

        b.cached_summary = summary
        b.cached_key_points = json.dumps(key_points)
        b.cached_at = datetime.now(UTC)
