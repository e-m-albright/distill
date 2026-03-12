"""Tests for bookmark service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus, StatusFilter
from app.services.bookmark_parser import BookmarkEntry
from app.services.bookmark_service import (
    discard_bookmarks,
    get_status_summary,
    ingest_bookmarks,
    list_bookmarks,
    move_bookmarks,
    purge_bookmarks,
    restore_bookmarks,
)


async def _seed(session: AsyncSession, count: int = 3) -> list[Bookmark]:
    """Insert test bookmarks and return them."""
    bookmarks = []
    for i in range(count):
        b = Bookmark(
            url=f"https://example.com/{i}",
            title=f"Bookmark {i}",
            folder="test",
            status=BookmarkStatus.UNREVIEWED,
        )
        session.add(b)
        bookmarks.append(b)
    await session.commit()
    for b in bookmarks:
        await session.refresh(b)
    return bookmarks


@pytest.mark.asyncio
async def test_list_bookmarks_with_status_filter(db_session: AsyncSession) -> None:
    """List bookmarks filters by status correctly."""
    bookmarks = await _seed(db_session)
    bookmarks[2].status = BookmarkStatus.DISCARD
    await db_session.commit()

    items, total = await list_bookmarks(db_session, status_filter=StatusFilter.ACTIVE)
    assert total == 2
    assert all(b.status == BookmarkStatus.UNREVIEWED for b in items)


@pytest.mark.asyncio
async def test_move_bookmarks(db_session: AsyncSession) -> None:
    """Move bookmarks to preview or view."""
    bookmarks = await _seed(db_session)
    ids = [bookmarks[0].id, bookmarks[1].id]

    moved = await move_bookmarks(db_session, ids, BookmarkStatus.VIEW)
    assert len(moved) == 2
    assert all(b.status == BookmarkStatus.VIEW for b in moved)


@pytest.mark.asyncio
async def test_discard_bookmarks(db_session: AsyncSession) -> None:
    """Discard sets status to DISCARD."""
    bookmarks = await _seed(db_session)
    discarded = await discard_bookmarks(db_session, [bookmarks[0].id])
    assert len(discarded) == 1
    assert discarded[0].status == BookmarkStatus.DISCARD


@pytest.mark.asyncio
async def test_restore_only_discarded(db_session: AsyncSession) -> None:
    """Restore only works on bookmarks in DISCARD status."""
    bookmarks = await _seed(db_session)
    bookmarks[0].status = BookmarkStatus.DISCARD
    await db_session.commit()

    restored = await restore_bookmarks(db_session, [b.id for b in bookmarks])
    assert len(restored) == 1
    assert restored[0].id == bookmarks[0].id
    assert restored[0].status == BookmarkStatus.UNREVIEWED


@pytest.mark.asyncio
async def test_purge_bookmarks(db_session: AsyncSession) -> None:
    """Purge permanently deletes only discarded bookmarks."""
    bookmarks = await _seed(db_session)
    bookmarks[0].status = BookmarkStatus.DISCARD
    await db_session.commit()

    count = await purge_bookmarks(db_session, [b.id for b in bookmarks])
    assert count == 1

    _, total = await list_bookmarks(db_session, status_filter=StatusFilter.ALL)
    assert total == 2


@pytest.mark.asyncio
async def test_ingest_deduplicates(db_session: AsyncSession) -> None:
    """Ingest skips URLs that already exist."""
    entries = [
        BookmarkEntry(url="https://example.com/1", title="First", folder="", added=None),
        BookmarkEntry(url="https://example.com/2", title="Second", folder="", added=None),
    ]
    new, total = await ingest_bookmarks(db_session, entries)
    assert new == 2
    assert total == 2

    entries2 = [
        BookmarkEntry(url="https://example.com/2", title="Second again", folder="", added=None),
        BookmarkEntry(url="https://example.com/3", title="Third", folder="", added=None),
    ]
    new2, total2 = await ingest_bookmarks(db_session, entries2)
    assert new2 == 1
    assert total2 == 2


@pytest.mark.asyncio
async def test_get_status_summary(db_session: AsyncSession) -> None:
    """Status summary returns correct counts."""
    bookmarks = await _seed(db_session)
    bookmarks[0].status = BookmarkStatus.DISCARD
    bookmarks[1].status = BookmarkStatus.VIEW
    await db_session.commit()

    summary = await get_status_summary(db_session)
    assert summary["total"] == 3
    assert summary["unreviewed"] == 1
    assert summary["view"] == 1
    assert summary["discard"] == 1
    assert summary["preview"] == 0
