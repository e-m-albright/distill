"""Shared bookmark CRUD operations. Used by both API routes and MCP tools."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus, StatusFilter, resolve_status_filter
from app.services.bookmark_parser import BookmarkEntry


async def list_bookmarks(
    session: AsyncSession,
    *,
    category: str | None = None,
    folder: str | None = None,
    status_filter: StatusFilter = StatusFilter.ACTIVE,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Bookmark], int]:
    """List bookmarks with filters. Returns (items, total_count)."""
    conditions = _build_conditions(status_filter, category, folder)

    count_result = await session.execute(
        select(func.count()).select_from(Bookmark).where(*conditions)
    )
    total = count_result.scalar() or 0

    result = await session.execute(
        select(Bookmark)
        .where(*conditions)
        .order_by(Bookmark.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(result.scalars().all())
    return items, total


async def move_bookmarks(
    session: AsyncSession,
    ids: list[int],
    target_status: BookmarkStatus,
) -> list[Bookmark]:
    """Move bookmarks to PREVIEW or VIEW. Returns the moved bookmarks."""
    if target_status not in (BookmarkStatus.PREVIEW, BookmarkStatus.VIEW):
        msg = f"move_bookmarks only supports PREVIEW and VIEW, got {target_status}"
        raise ValueError(msg)
    moved = []
    for bid in ids:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
        b = result.scalar_one_or_none()
        if b:
            b.status = target_status
            moved.append(b)
    await session.commit()
    return moved


async def discard_bookmarks(
    session: AsyncSession,
    ids: list[int],
) -> list[Bookmark]:
    """Soft-delete bookmarks by setting status to DISCARD."""
    discarded = []
    for bid in ids:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
        b = result.scalar_one_or_none()
        if b:
            b.status = BookmarkStatus.DISCARD
            discarded.append(b)
    await session.commit()
    return discarded


async def restore_bookmarks(
    session: AsyncSession,
    ids: list[int],
) -> list[Bookmark]:
    """Restore bookmarks from DISCARD to UNREVIEWED. Only restores items currently in DISCARD."""
    restored = []
    for bid in ids:
        result = await session.execute(
            select(Bookmark).where(
                Bookmark.id == bid,
                Bookmark.status == BookmarkStatus.DISCARD,
            )
        )
        b = result.scalar_one_or_none()
        if b:
            b.status = BookmarkStatus.UNREVIEWED
            restored.append(b)
    await session.commit()
    return restored


async def purge_bookmarks(
    session: AsyncSession,
    ids: list[int],
) -> int:
    """Permanently delete bookmarks in DISCARD status. Returns count deleted."""
    purged = 0
    for bid in ids:
        result = await session.execute(
            select(Bookmark).where(
                Bookmark.id == bid,
                Bookmark.status == BookmarkStatus.DISCARD,
            )
        )
        b = result.scalar_one_or_none()
        if b:
            await session.delete(b)
            purged += 1
    await session.commit()
    return purged


async def get_status_summary(session: AsyncSession) -> dict[str, int]:
    """Return bookmark counts by status."""
    total_r = await session.execute(select(func.count()).select_from(Bookmark))
    total = total_r.scalar() or 0

    summary: dict[str, int] = {"total": total}
    for status in BookmarkStatus:
        count_r = await session.execute(
            select(func.count()).select_from(Bookmark).where(Bookmark.status == status)
        )
        summary[status.value] = count_r.scalar() or 0
    return summary


async def get_bookmark_by_id(session: AsyncSession, bookmark_id: int) -> Bookmark | None:
    """Get a single bookmark by ID."""
    result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
    return result.scalar_one_or_none()


async def ingest_bookmarks(
    session: AsyncSession,
    entries: list[BookmarkEntry],
) -> tuple[int, int]:
    """Ingest bookmark entries, deduplicating by URL. Returns (new_count, total_entries)."""
    new_count = 0
    for entry in entries:
        if not entry.url or not entry.url.startswith("http"):
            continue
        result = await session.execute(select(Bookmark).where(Bookmark.url == entry.url))
        if result.scalar_one_or_none() is None:
            session.add(
                Bookmark(
                    url=entry.url,
                    title=entry.title,
                    folder=entry.folder,
                    added=entry.added,
                    status=BookmarkStatus.UNREVIEWED,
                )
            )
            new_count += 1
    await session.commit()
    return new_count, len(entries)


def _build_conditions(
    status_filter: StatusFilter,
    category: str | None = None,
    folder: str | None = None,
) -> list:
    """Build SQLAlchemy WHERE conditions from filters."""
    conditions: list = []
    resolved = resolve_status_filter(status_filter)
    if resolved is not None:
        if len(resolved) == 1:
            conditions.append(Bookmark.status == resolved[0])
        else:
            conditions.append(Bookmark.status.in_([s.value for s in resolved]))
    if category:
        conditions.append(Bookmark.category == category)
    if folder:
        conditions.append(Bookmark.folder == folder)
    return conditions
