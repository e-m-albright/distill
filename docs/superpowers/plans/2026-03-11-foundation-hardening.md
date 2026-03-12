# Foundation Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve code quality, architecture, and test coverage without changing user-visible behavior.

**Architecture:** Extract a `BookmarkStatus` StrEnum as single source of truth for status values. Decompose the 722-line MCP server monolith into focused tool modules. Extract shared bookmark CRUD operations into `bookmark_service.py` so API routes and MCP tools both call the same functions. Add per-item error handling in distill. Add ~19 critical-path tests.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, FastMCP, Pydantic v2, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-11-foundation-hardening-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `app/models/status.py` | `BookmarkStatus` enum (4 DB values), `StatusFilter` enum (8 query values), `resolve_status_filter()` helper |
| `app/services/bookmark_service.py` | Shared CRUD: list, move, discard, restore, purge, ingest, status summary |
| `app/mcp/__init__.py` | Empty package init |
| `app/mcp/constants.py` | Shared constants: URI strings, CSP, permissions, HTML loader. Imported by both `server.py` and tool modules to avoid circular imports. |
| `app/mcp/server.py` | FastMCP app creation, resource registration, logging setup, tool module registration |
| `app/mcp/tools/__init__.py` | Empty package init |
| `app/mcp/tools/ingest.py` | `ingest_bookmarks` MCP tool |
| `app/mcp/tools/organize.py` | `organize_bookmarks`, `list_groups` MCP tools |
| `app/mcp/tools/triage.py` | `list_bookmarks`, `list_folders`, `triage`, `list_by_status`, `get_status_summary`, `reconcile_status`, `verify_bookmark_status` MCP tools |
| `app/mcp/tools/preview.py` | `preview`, `summarize_bookmark` MCP tools |
| `app/mcp/tools/manage.py` | `move_to_preview`, `move_to_view`, `discard_bookmarks`, `suggest_discard`, `restore_from_discard`, `purge_bookmarks` MCP tools |
| `app/mcp/tools/view.py` | `list_view` MCP tool |
| `tests/test_status.py` | Status enum + filter resolution tests |
| `tests/test_bookmark_service.py` | Bookmark service CRUD tests |
| `tests/test_cache_service.py` | Cache hit/miss/expiry tests |
| `tests/test_api_bookmarks.py` | API route integration tests |

### Modified Files
| File | Changes |
|------|---------|
| `app/models/bookmark.py` | Import and use `BookmarkStatus` for default value |
| `app/schemas/distill.py` | No changes needed (status field stays `str` for JSON compat) |
| `app/api/routes/bookmarks.py` | Replace inline DB logic with `bookmark_service` calls, use `StatusFilter` enum |
| `app/api/routes/ingest.py` | Replace inline ingest logic with `bookmark_service.ingest_bookmarks()` call |
| `app/services/cache_service.py` | No changes needed |
| `app/services/distill_service.py` | Add per-item error handling in `distill_content()` |
| `app/db/session.py` | Rename migration functions for clarity |
| `app/mcp_server.py` | Reduce to thin re-export of `app.mcp.server:mcp` |
| `justfile` | Update MCP command to use `app.mcp.server` |
| `tests/test_bookmark_parser.py` | Add edge case tests |

---

## Chunk 1: Status Enum & Bookmark Service

### Task 1: Create Status Enum

**Files:**
- Create: `app/models/status.py`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_status.py`:

```python
"""Tests for status enum and filter resolution."""

from app.models.status import BookmarkStatus, StatusFilter, resolve_status_filter


def test_resolve_active_returns_unreviewed() -> None:
    """'active' filter resolves to [UNREVIEWED]."""
    result = resolve_status_filter(StatusFilter.ACTIVE)
    assert result == [BookmarkStatus.UNREVIEWED]


def test_resolve_kept_returns_non_discard() -> None:
    """'kept' filter resolves to all non-discard statuses."""
    result = resolve_status_filter(StatusFilter.KEPT)
    assert set(result) == {BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW}


def test_resolve_all_returns_none() -> None:
    """'all' filter resolves to None (no filter)."""
    result = resolve_status_filter(StatusFilter.ALL)
    assert result is None


def test_resolve_discarded_alias() -> None:
    """'discarded' legacy alias resolves same as 'discard'."""
    result = resolve_status_filter(StatusFilter.DISCARDED)
    assert result == [BookmarkStatus.DISCARD]


def test_resolve_direct_status() -> None:
    """Direct status values resolve to themselves."""
    assert resolve_status_filter(StatusFilter.PREVIEW) == [BookmarkStatus.PREVIEW]
    assert resolve_status_filter(StatusFilter.VIEW) == [BookmarkStatus.VIEW]
    assert resolve_status_filter(StatusFilter.DISCARD) == [BookmarkStatus.DISCARD]
    assert resolve_status_filter(StatusFilter.UNREVIEWED) == [BookmarkStatus.UNREVIEWED]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.status'`

- [ ] **Step 3: Create the status module**

Create `app/models/status.py`:

```python
"""Bookmark status enum and filter resolution."""

from enum import StrEnum


class BookmarkStatus(StrEnum):
    """Real DB status values. Used for writing/storing."""

    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"


class StatusFilter(StrEnum):
    """Valid query parameter values. Used only for reads/queries."""

    ACTIVE = "active"
    KEPT = "kept"
    ALL = "all"
    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"
    DISCARDED = "discarded"


def resolve_status_filter(f: StatusFilter) -> list[BookmarkStatus] | None:
    """Map a StatusFilter to DB conditions. Returns None for ALL (no filter)."""
    if f == StatusFilter.ALL:
        return None
    if f == StatusFilter.ACTIVE:
        return [BookmarkStatus.UNREVIEWED]
    if f == StatusFilter.KEPT:
        return [BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW]
    if f in (StatusFilter.DISCARD, StatusFilter.DISCARDED):
        return [BookmarkStatus.DISCARD]
    # Direct match: UNREVIEWED, PREVIEW, VIEW
    return [BookmarkStatus(f.value)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_status.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Update bookmark model to use enum**

In `app/models/bookmark.py`, change the status default:

```python
# Add import at top:
from app.models.status import BookmarkStatus

# Change line 21-23 from:
#     status: Mapped[str] = mapped_column(
#         String(32), default="unreviewed"
#     )
# To:
    status: Mapped[str] = mapped_column(
        String(32), default=BookmarkStatus.UNREVIEWED
    )
```

- [ ] **Step 6: Verify existing tests still pass**

Run: `uv run pytest -v`
Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/models/status.py tests/test_status.py app/models/bookmark.py
git commit -m "feat: add BookmarkStatus and StatusFilter enums with resolver"
```

---

### Task 2: Create Bookmark Service

**Files:**
- Create: `app/services/bookmark_service.py`
- Test: `tests/test_bookmark_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bookmark_service.py`:

```python
"""Tests for bookmark service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus, StatusFilter
from app.services.bookmark_service import (
    discard_bookmarks,
    get_status_summary,
    ingest_bookmarks,
    list_bookmarks,
    move_bookmarks,
    purge_bookmarks,
    restore_bookmarks,
)
from app.services.bookmark_parser import BookmarkEntry


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
    # Discard one, leave others as unreviewed
    bookmarks[0].status = BookmarkStatus.DISCARD
    await db_session.commit()

    restored = await restore_bookmarks(db_session, [b.id for b in bookmarks])
    # Only the discarded one should be restored
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
    assert count == 1  # Only the discarded one

    # Verify it's gone
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

    # Ingest again with overlap
    entries2 = [
        BookmarkEntry(url="https://example.com/2", title="Second again", folder="", added=None),
        BookmarkEntry(url="https://example.com/3", title="Third", folder="", added=None),
    ]
    new2, total2 = await ingest_bookmarks(db_session, entries2)
    assert new2 == 1  # Only the new one
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bookmark_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.bookmark_service'`

- [ ] **Step 3: Create the bookmark service**

Create `app/services/bookmark_service.py`:

```python
"""Shared bookmark CRUD operations. Used by both API routes and MCP tools."""

from sqlalchemy import delete, func, select
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bookmark_service.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/bookmark_service.py tests/test_bookmark_service.py
git commit -m "feat: add bookmark_service with shared CRUD operations"
```

---

### Task 3: Add Cache Service Tests

**Files:**
- Create: `tests/test_cache_service.py`

- [ ] **Step 1: Write the cache tests**

Create `tests/test_cache_service.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_cache_service.py -v`
Expected: All 3 tests PASS (these test existing code)

- [ ] **Step 3: Commit**

```bash
git add tests/test_cache_service.py
git commit -m "test: add cache service tests (hit, miss, expiry)"
```

---

### Task 4: Add Bookmark Parser Edge Case Tests

**Files:**
- Modify: `tests/test_bookmark_parser.py`

- [ ] **Step 1: Add edge case tests**

Append to `tests/test_bookmark_parser.py`:

```python


def test_parse_netscape_html_empty() -> None:
    """Empty/minimal HTML returns no entries."""
    entries = list(parse_netscape_html(""))
    assert entries == []


def test_parse_netscape_html_no_links() -> None:
    """HTML with no links returns no entries."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><H3>Empty Folder</H3><DL></DL></DL>"""
    entries = list(parse_netscape_html(html))
    assert entries == []


def test_parse_chrome_json_empty_roots() -> None:
    """Chrome JSON with empty roots returns no entries."""
    data = '{"roots": {"bookmark_bar": {"children": []}}}'
    entries = list(parse_chrome_json(data))
    assert entries == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_bookmark_parser.py -v`
Expected: All 5 tests PASS (2 existing + 3 new)

- [ ] **Step 3: Commit**

```bash
git add tests/test_bookmark_parser.py
git commit -m "test: add bookmark parser edge case tests"
```

---

## Chunk 2: MCP Server Decomposition

### Task 5: Create MCP Package Structure

**Files:**
- Create: `app/mcp/__init__.py`
- Create: `app/mcp/server.py`
- Create: `app/mcp/tools/__init__.py`

- [ ] **Step 1: Create the MCP constants module (avoids circular imports)**

Create `app/mcp/__init__.py` (empty):

```python
```

Create `app/mcp/tools/__init__.py` (empty):

```python
```

Create `app/mcp/constants.py` — shared constants imported by both `server.py` and tool modules:

```python
"""Shared MCP constants. Imported by server.py and tool modules to avoid circular imports."""

from pathlib import Path

from fastmcp.server.apps import ResourceCSP, ResourcePermissions

# Path to mcp-app HTML files (project root / mcp-app)
MCP_APP_DIR = Path(__file__).resolve().parent.parent.parent / "mcp-app"

TRIAGE_URI = "ui://distillation/triage.html"
PREVIEW_URI = "ui://distillation/preview.html"
VIEW_URI = "ui://distillation/view.html"

CSP = ResourceCSP(resource_domains=["https://unpkg.com"])
PERMS = ResourcePermissions(clipboard_write={})


def load_html(name: str) -> str:
    """Load an HTML file from the mcp-app directory."""
    path = MCP_APP_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""
```

- [ ] **Step 2: Create the MCP server module**

Create `app/mcp/server.py`:

```python
"""MCP server for Claude Desktop — interactive bookmark distillation."""

import asyncio
import logging
import sys

import structlog
from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig

from app.mcp.constants import CSP, PERMS, PREVIEW_URI, TRIAGE_URI, VIEW_URI, load_html


# MCP uses stdio for JSON-RPC; stdout must be clean. Route all logs to stderr.
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)


mcp = FastMCP(
    name="Distillation",
    instructions="""You help the user chew through their bookmarks and tame information overload.

Workflow: Ingest -> Organize -> Triage -> Preview (per-link) -> Move to View or Discard.

1. Ingest bookmarks. Run list_groups to see Total | Organized | Unorganized. Groups = organized only; unorganized have no category yet.
2. Organize: Run organize_bookmarks repeatedly until Unorganized is 0. Each run assigns categories to up to 500 unorganized bookmarks. Already-categorized are left unchanged (stable counts).
3. Triage: Run triage or list_bookmarks. Present links for review. Do NOT auto-discard. Use suggest_discard to present candidates; wait for user confirmation before discard_bookmarks.
4. Preview: Run preview to fetch and summarize (per-link). Confirm with user which links to preview vs put aside for view.
5. Move to View: Links user wants to visit go to view. Use move_to_preview for AI summarization.

Always run list_groups first to show the full picture (total, organized, unorganized). Run organize_bookmarks multiple times until all are categorized. Do not discard, preview, or move links without explicit user confirmation.

Always show URLs as markdown links [title](url). Be flexible: create groups, extract value per link, present findings, write artifacts when requested.""",
)

# Register all tool modules
from app.mcp.tools import ingest, manage, organize, preview, triage, view

for module in [ingest, organize, triage, preview, manage, view]:
    module.register(mcp)


# Register UI resources
@mcp.resource(TRIAGE_URI, app=AppConfig(csp=CSP, permissions=PERMS))
def triage_view() -> str:
    """Triage UI resource."""
    return load_html("triage.html")


@mcp.resource(PREVIEW_URI, app=AppConfig(csp=CSP, permissions=PERMS))
def preview_view() -> str:
    """Preview UI resource (post-preview)."""
    return load_html("preview.html")


@mcp.resource(VIEW_URI, app=AppConfig(csp=CSP, permissions=PERMS))
def view_view() -> str:
    """View UI resource (links to visit)."""
    return load_html("view.html")


def main() -> None:
    """CLI entry point for MCP server."""
    asyncio.run(_init_and_run())


async def _init_and_run() -> None:
    from app.db.session import init_db

    await init_db()
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit the skeleton**

```bash
git add app/mcp/__init__.py app/mcp/constants.py app/mcp/server.py app/mcp/tools/__init__.py
git commit -m "refactor: create MCP package skeleton with server setup"
```

---

### Task 6: Create MCP Tool Modules

**Files:**
- Create: `app/mcp/tools/ingest.py`
- Create: `app/mcp/tools/organize.py`
- Create: `app/mcp/tools/triage.py`
- Create: `app/mcp/tools/preview.py`
- Create: `app/mcp/tools/manage.py`
- Create: `app/mcp/tools/view.py`

- [ ] **Step 1: Create ingest tool module**

Create `app/mcp/tools/ingest.py`:

```python
"""MCP tools for bookmark ingestion."""

from pathlib import Path

from fastmcp import FastMCP

from app.db.session import async_session
from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html
from app.services.bookmark_service import ingest_bookmarks as svc_ingest


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def ingest_bookmarks(file_path: str, format: str = "html") -> str:
        """Ingest a bookmark export file. Pass the full path (e.g. ~/Downloads/bookmarks.html).
        Format: 'html' for Netscape/Chrome HTML export, 'json' for Chrome JSON."""
        path = Path(file_path).expanduser()  # noqa: ASYNC240
        if not path.exists():
            return f"File not found: {path}"
        content = path.read_text(encoding="utf-8", errors="replace")
        if format == "json":
            entries = list(parse_chrome_json(content))
        else:
            entries = list(parse_netscape_html(content))

        async with async_session() as session:
            ingested, total = await svc_ingest(session, entries)
        return f"Ingested {ingested} new bookmarks from {total} total in file."
```

- [ ] **Step 2: Create organize tool module**

Create `app/mcp/tools/organize.py`:

```python
"""MCP tools for bookmark organization."""

from fastmcp import FastMCP
from sqlalchemy import func, or_, select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.services.organize_service import organize_bookmarks as organize_service


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def organize_bookmarks(categories: list[str]) -> str:
        """Assign UNORGANIZED active bookmarks to user-defined groups. Only processes bookmarks with no category yet (incremental).
        Categories are labels like: low_value, high_value, AI, cooking, parenting, work, news, etc.
        Run repeatedly until unorganized count is 0. Each run processes up to 500 unorganized bookmarks."""
        if len(categories) < 2:
            return "Provide at least 2 categories, e.g. ['low_value', 'high_value', 'AI', 'cooking']"
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(
                    Bookmark.status == BookmarkStatus.UNREVIEWED,
                    or_(Bookmark.category == "", Bookmark.category.is_(None)),
                )
                .limit(500)
            )
            bookmarks = result.scalars().all()
        if not bookmarks:
            return "No unorganized bookmarks left. All unreviewed bookmarks already have categories."
        items = [(b.id, b.title, b.url, b.folder) for b in bookmarks]
        assignments = await organize_service(items, categories)
        async with async_session() as session:
            for bid, cat in assignments:
                result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
                b = result.scalar_one_or_none()
                if b:
                    b.category = cat
            await session.commit()
        counts: dict[str, int] = {}
        for _, cat in assignments:
            counts[cat] = counts.get(cat, 0) + 1
        async with async_session() as session:
            remaining = await session.scalar(
                select(func.count())
                .select_from(Bookmark)
                .where(
                    Bookmark.status == BookmarkStatus.UNREVIEWED,
                    or_(Bookmark.category == "", Bookmark.category.is_(None)),
                )
            ) or 0
        lines = [f"Organized {len(assignments)} bookmarks into {len(categories)} groups:"]
        for c in categories:
            lines.append(f"- {c}: {counts.get(c, 0)}")
        lines.append(
            f"\nUnorganized remaining: {remaining}. Run again to process more."
            if remaining
            else "\nAll bookmarks organized."
        )
        return "\n".join(lines)

    @mcp.tool
    async def list_groups() -> str:
        """List bookmark category counts. Shows TOTAL, ORGANIZED, and UNORGANIZED so you know the full picture.
        Groups = organized only. Unorganized bookmarks have no category yet — run organize_bookmarks to assign them (500 per run)."""
        kept_statuses = [BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW]
        async with async_session() as session:
            total = await session.scalar(
                select(func.count()).select_from(Bookmark).where(
                    Bookmark.status.in_(kept_statuses)
                )
            ) or 0
            unorg = await session.scalar(
                select(func.count())
                .select_from(Bookmark)
                .where(
                    Bookmark.status.in_(kept_statuses),
                    or_(Bookmark.category == "", Bookmark.category.is_(None)),
                )
            ) or 0
            result = await session.execute(
                select(Bookmark.category, func.count())
                .where(
                    Bookmark.status.in_(kept_statuses),
                    Bookmark.category != "",
                )
                .group_by(Bookmark.category)
                .order_by(Bookmark.category)
            )
            rows = result.fetchall()
        organized = sum(n for _, n in rows)
        async with async_session() as session:
            discard_count = await session.scalar(
                select(func.count()).select_from(Bookmark).where(
                    Bookmark.status == BookmarkStatus.DISCARD
                )
            ) or 0
            view_count = await session.scalar(
                select(func.count()).select_from(Bookmark).where(
                    Bookmark.status == BookmarkStatus.VIEW
                )
            ) or 0
        lines = [
            f"Total: {total} | Discard: {discard_count} | View: {view_count} | Organized: {organized} | Unorganized: {unorg}",
            "",
            "Groups (organized only):",
        ]
        lines.extend(f"- {cat}: {n}" for cat, n in rows)
        if not rows:
            return f"Total: {total} | Unorganized: {unorg}\n\nNo groups yet. Run organize_bookmarks with your categories."
        return "\n".join(lines)
```

- [ ] **Step 3: Create triage tool module**

Create `app/mcp/tools/triage.py`:

```python
"""MCP tools for bookmark triage and status inspection."""

import json

from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig
from sqlalchemy import func, select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus, StatusFilter, resolve_status_filter
from app.mcp.constants import CSP, PERMS, TRIAGE_URI


def _status_where(status: str) -> list:
    """Resolve status string to SQLAlchemy WHERE conditions."""
    try:
        sf = StatusFilter(status)
    except ValueError:
        return [Bookmark.status == status]
    resolved = resolve_status_filter(sf)
    if resolved is None:
        return []
    if len(resolved) == 1:
        return [Bookmark.status == resolved[0]]
    return [Bookmark.status.in_([s.value for s in resolved])]


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def list_bookmarks(
        category: str | None = None,
        folder: str | None = None,
        status: str = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """List stored bookmarks (title + URL only). Use for triage: review by title/URL.
        Status: active (unreviewed only), kept (all non-discard), discard, unreviewed, preview, view, all.
        Category and folder use exact match. Filters combine (AND)."""
        status_filter = _status_where(status)
        category_filter = [Bookmark.category == category] if category else []
        folder_filter = [Bookmark.folder == folder] if folder else []

        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(*status_filter, *category_filter, *folder_filter)
                .order_by(Bookmark.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            items = result.scalars().all()
            count_result = await session.execute(
                select(func.count())
                .select_from(Bookmark)
                .where(*status_filter, *category_filter, *folder_filter)
            )
            total = count_result.scalar() or 0

        if not items:
            return "No bookmarks found."
        lines = [
            f"Total: {total} | Showing {len(items)} (IDs for discard_bookmarks, move_to_preview, move_to_view)"
        ]
        for b in items:
            cat = f" | {b.category}" if b.category else ""
            lines.append(f"- [{b.id}] [{b.title}]({b.url}){cat}")
        return "\n".join(lines)

    @mcp.tool
    async def list_folders() -> str:
        """List all bookmark folder paths (from browser export). Use to see structure before organizing."""
        kept_statuses = [BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW]
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark.folder)
                .where(
                    Bookmark.status.in_(kept_statuses),
                    Bookmark.folder != "",
                )
                .distinct()
                .order_by(Bookmark.folder)
            )
            folders = [r[0] for r in result.fetchall()]
        if not folders:
            return "No folders found (bookmarks may be in root). Use list_bookmarks to see all."
        return "Folders:\n" + "\n".join(f"- {f}" for f in folders)

    @mcp.tool(app=AppConfig(resource_uri=TRIAGE_URI, csp=CSP, permissions=PERMS))
    async def triage(
        category: str | None = None,
        folder: str | None = None,
        status: str = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """Show triage UI: list bookmarks by title/URL for review. Same filters as list_bookmarks."""
        status_filter = _status_where(status)
        category_filter = [Bookmark.category == category] if category else []
        folder_filter = [Bookmark.folder == folder] if folder else []

        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(*status_filter, *category_filter, *folder_filter)
                .order_by(Bookmark.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            items = result.scalars().all()

        if not items:
            return json.dumps({"items": [], "category": category or ""})

        data = {
            "items": [{"id": b.id, "title": b.title or "", "url": b.url} for b in items],
            "category": category or "",
        }
        return json.dumps(data)

    @mcp.tool
    async def list_by_status(
        status_filter: str = "all",
        limit: int = 500,
    ) -> str:
        """Debug: List ALL bookmarks by status across all categories. Shows id, status, category, title, url.
        status_filter: active, kept, unreviewed, preview, view, discard, all.
        Use to verify distribution and find missing bookmarks."""
        status_where = _status_where(status_filter)
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(*status_where)
                .order_by(Bookmark.status, Bookmark.category, Bookmark.id)
                .limit(limit)
            )
            items = result.scalars().all()
            total_result = await session.execute(
                select(func.count()).select_from(Bookmark).where(*status_where)
            )
            total = total_result.scalar() or 0

        if not items:
            return f"No bookmarks with status '{status_filter}'."
        lines = [
            f"Total: {total} | Showing {len(items)} (status_filter={status_filter})",
            "",
            "Format: [id] status=... | category | [title](url)",
            "",
        ]
        for b in items:
            st = b.status or "(null)"
            cat = b.category or "(none)"
            lines.append(f"- [{b.id}] status={st} | {cat} | [{b.title or '(no title)'}]({b.url})")
        if total > limit:
            lines.append(f"\n(Truncated at {limit}. Pass limit={total} to see all.)")
        return "\n".join(lines)

    @mcp.tool
    async def reconcile_status(bookmark_id: int) -> str:
        """Debug: Verify the actual status of a bookmark in the backend. Use to confirm move operations."""
        async with async_session() as session:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
            b = result.scalar_one_or_none()
        if not b:
            return f"Bookmark {bookmark_id} not found."
        created = b.created_at.isoformat() if b.created_at else "(unknown)"
        return (
            f"Bookmark {bookmark_id}: status={b.status!r} | category={b.category or '(none)'} | "
            f"created_at={created} | [{b.title or '(no title)'}]({b.url})"
        )

    @mcp.tool
    async def verify_bookmark_status(bookmark_id: int) -> str:
        """Debug: Same as reconcile_status. Returns id, current_status, created_at, category for verification."""
        return await reconcile_status(bookmark_id)

    @mcp.tool
    async def get_status_summary() -> str:
        """Debug: Reconciliation report. Shows status distribution across all bookmarks.
        Use to verify move operations and identify accounting discrepancies."""
        async with async_session() as session:
            total_result = await session.execute(select(func.count()).select_from(Bookmark))
            total = total_result.scalar() or 0

            counts = {}
            for status in BookmarkStatus:
                r = await session.execute(
                    select(func.count()).select_from(Bookmark).where(Bookmark.status == status)
                )
                counts[status.value] = r.scalar() or 0

        summed = sum(counts.values())
        other = total - summed

        lines = [
            "Status summary (reconciliation report):",
            "",
            f"  total:     {total}",
            f"  active:    {counts.get('unreviewed', 0)}  (unreviewed/organized, not yet moved)",
            f"  preview:   {counts.get('preview', 0)}",
            f"  view:      {counts.get('view', 0)}",
            f"  discard:   {counts.get('discard', 0)}",
            "",
            f"  sum:       {summed}",
        ]
        if other != 0:
            lines.append(f"  other:     {other}  (unexpected status values)")
        if total != summed + other:
            lines.append(f"  WARNING: sum ({summed}) != total ({total})")
        return "\n".join(lines)
```

- [ ] **Step 4: Create preview tool module**

Create `app/mcp/tools/preview.py`:

```python
"""MCP tools for bookmark preview and summarization."""

import asyncio
import json

from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig
from sqlalchemy import select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.mcp.constants import CSP, PERMS, PREVIEW_URI
from app.services.cache_service import get_cached_summary, update_cache
from app.services.content_fetcher import ExtractedContent, fetch_and_extract
from app.services.distill_service import distill_content, summarize_single


def register(mcp: FastMCP) -> None:
    @mcp.tool(app=AppConfig(resource_uri=PREVIEW_URI, csp=CSP, permissions=PERMS))
    async def preview(
        limit: int = 20,
        category: str | None = None,
        folder: str | None = None,
        use_cache: bool = True,
    ) -> str:
        """Run preview: fetch and summarize each link (per-link, no overview). Filter by category or folder.
        Confirm with user which links to preview before running. Cached summaries reused when use_cache=True."""
        from datetime import UTC, datetime, timedelta

        cat_filter = [Bookmark.category == category] if category else []
        folder_filter = [Bookmark.folder == folder] if folder else []
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(
                    Bookmark.status.in_([BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW]),
                    *cat_filter,
                    *folder_filter,
                )
                .limit(limit)
            )
            bookmarks = result.scalars().all()

        if not bookmarks:
            return "No unreviewed or preview bookmarks. Ingest and organize first."

        sem = asyncio.Semaphore(10)

        async def get_content(b: Bookmark) -> ExtractedContent:
            if use_cache and b.cached_summary and b.cached_at:
                cutoff = datetime.now(UTC) - timedelta(days=30)
                fresh = (
                    b.cached_at.replace(tzinfo=UTC) if b.cached_at.tzinfo is None else b.cached_at
                ) >= cutoff
                if fresh:
                    return ExtractedContent(
                        url=b.url,
                        title=b.title,
                        text=b.cached_summary,
                        success=True,
                        source="html",
                    )
            async with sem:
                return await fetch_and_extract(b.url)

        contents = await asyncio.gather(*[get_content(b) for b in bookmarks])
        brief = await distill_content(list(contents))

        # Write cache
        async with async_session() as session:
            for i in brief.items:
                await update_cache(session, i.url, i.summary, i.key_points)
            await session.commit()

        # Map url -> bookmark id for UI
        url_to_id = {b.url: b.id for b in bookmarks}
        items = [
            {
                "id": url_to_id.get(i.url, 0),
                "title": i.title,
                "url": i.url,
                "summary": i.summary,
                "key_points": i.key_points or [],
                "view": i.view,
            }
            for i in brief.items
        ]
        return json.dumps({"items": items})

    @mcp.tool
    async def summarize_bookmark(url: str) -> str:
        """Fetch and summarize a single URL. Uses cached summary when available (no re-fetch, no tokens)."""
        if not url.startswith("http"):
            return "URL must start with http or https."
        async with async_session() as session:
            cached = await get_cached_summary(session, url)
        if cached:
            summary, key_points = cached
            pts = "\n- " + "\n  - ".join(key_points) if key_points else ""
            return f"**[Cached]** [{url}]({url})\n\nSummary: {summary}\n\nKey points:{pts}"
        item = await summarize_single(url)
        # Cache the result
        async with async_session() as session:
            await update_cache(session, url, item.summary, item.key_points)
            await session.commit()
        pts = "\n- " + "\n- ".join(item.key_points) if item.key_points else ""
        return f"**[{item.title}]({item.url})**\n\nSummary: {item.summary}\n\nKey points:{pts}"
```

- [ ] **Step 5: Create manage tool module**

Create `app/mcp/tools/manage.py`:

```python
"""MCP tools for bookmark management (move, discard, restore, purge)."""

from fastmcp import FastMCP
from sqlalchemy import select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.services.bookmark_service import (
    discard_bookmarks as svc_discard,
    get_bookmark_by_id,
    move_bookmarks as svc_move,
    purge_bookmarks as svc_purge,
    restore_bookmarks as svc_restore,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def discard_bookmarks(bookmark_ids: list[int]) -> str:
        """Bulk discard bookmarks. Pass a list of IDs from list_bookmarks."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            discarded = await svc_discard(session, bookmark_ids)
        if not discarded:
            return "No bookmarks found with those IDs."
        lines = [f"Discarded {len(discarded)} bookmarks:"]
        for b in discarded:
            lines.append(f"- {b.id}: {b.title}")
        return "\n".join(lines)

    @mcp.tool
    async def move_to_preview(bookmark_ids: list[int]) -> str:
        """Move bookmarks to preview status (for AI fetch/summarize). Only when user confirms."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            moved = await svc_move(session, bookmark_ids, BookmarkStatus.PREVIEW)
        if not moved:
            return "No bookmarks found with those IDs."
        lines = [f"Moved {len(moved)} bookmarks to preview:"]
        for b in moved:
            lines.append(f"- {b.id}: {b.title}")
        return "\n".join(lines)

    @mcp.tool
    async def move_to_view(bookmark_ids: list[int]) -> str:
        """Move bookmarks to view status (user's collection to visit). Only when user confirms."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            moved = await svc_move(session, bookmark_ids, BookmarkStatus.VIEW)
        if not moved:
            return "No bookmarks found with those IDs."
        lines = [f"Moved {len(moved)} bookmarks to view:"]
        for b in moved:
            lines.append(f"- {b.id}: {b.title}")
        return "\n".join(lines)

    @mcp.tool
    async def suggest_discard(bookmark_ids: list[int]) -> str:
        """Present these bookmark IDs as suggested discards. Does NOT discard—format for user to review.
        Only call discard_bookmarks when user explicitly confirms."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID to suggest for discard."
        async with async_session() as session:
            items: list[tuple[int, str, str]] = []
            for bid in bookmark_ids:
                b = await get_bookmark_by_id(session, bid)
                if b:
                    items.append((b.id, b.title, b.url))
        if not items:
            return "No bookmarks found with those IDs."
        lines = [
            "Suggested for discard (confirm before discarding):",
            "",
        ]
        for bid, title, url in items:
            lines.append(f"- [{bid}] [{title}]({url})")
        lines.append("")
        lines.append("If user confirms, call discard_bookmarks with the IDs above.")
        return "\n".join(lines)

    @mcp.tool
    async def purge_bookmarks(bookmark_ids: list[int]) -> str:
        """Permanently delete soft-deleted bookmarks. Only purges items in discard status.
        Irreversible. Use after reviewing list_bookmarks(status='discard')."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            count = await svc_purge(session, bookmark_ids)
        if not count:
            return "No discarded bookmarks found with those IDs. Only soft-deleted (discard) items can be purged."
        return f"Purged {count} bookmarks (permanently deleted)."

    @mcp.tool
    async def restore_from_discard(bookmark_ids: list[int]) -> str:
        """Restore soft-deleted bookmarks from discard back to unreviewed."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            restored = await svc_restore(session, bookmark_ids)
        if not restored:
            return "No discarded bookmarks found with those IDs."
        lines = [f"Restored {len(restored)} bookmarks to unreviewed:"]
        for b in restored:
            lines.append(f"- {b.id}: {b.title}")
        return "\n".join(lines)
```

- [ ] **Step 6: Create view tool module**

Create `app/mcp/tools/view.py`:

```python
"""MCP tools for viewing the curated bookmark collection."""

import json

from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig
from sqlalchemy import select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.mcp.constants import CSP, PERMS, VIEW_URI


def register(mcp: FastMCP) -> None:
    @mcp.tool(app=AppConfig(resource_uri=VIEW_URI, csp=CSP, permissions=PERMS))
    async def list_view(
        limit: int = 100,
    ) -> str:
        """Show View UI: links in your collection to visit. Run to display the view list."""
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark)
                .where(Bookmark.status == BookmarkStatus.VIEW)
                .order_by(Bookmark.created_at.desc())
                .limit(limit)
            )
            items = result.scalars().all()
        if not items:
            return json.dumps({"items": []})
        data = {
            "items": [{"id": b.id, "title": b.title or "", "url": b.url} for b in items],
        }
        return json.dumps(data)
```

- [ ] **Step 7: Commit tool modules**

```bash
git add app/mcp/tools/ingest.py app/mcp/tools/organize.py app/mcp/tools/triage.py app/mcp/tools/preview.py app/mcp/tools/manage.py app/mcp/tools/view.py
git commit -m "refactor: create MCP tool modules (ingest, organize, triage, preview, manage, view)"
```

---

### Task 7: Replace Old MCP Server with Re-export

**Files:**
- Modify: `app/mcp_server.py`
- Modify: `justfile`

- [ ] **Step 1: Replace mcp_server.py with re-export**

Replace the entire contents of `app/mcp_server.py` with:

```python
"""Backwards-compatible entry point. Delegates to app.mcp.server."""

from app.mcp.server import main, mcp

__all__ = ["main", "mcp"]

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update justfile MCP command**

In `justfile`, change line 48-49 from:
```
mcp:
    uv run python -m app.mcp_server
```
To:
```
mcp:
    uv run python -m app.mcp.server
```

- [ ] **Step 3: Verify the app still starts**

Run: `uv run python -c "from app.mcp.server import mcp; print('MCP server loaded:', mcp.name)"`
Expected: `MCP server loaded: Distillation`

- [ ] **Step 4: Verify existing tests still pass**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/mcp_server.py justfile
git commit -m "refactor: replace mcp_server.py with thin re-export of app.mcp.server"
```

---

## Chunk 3: Unify REST API & MCP Logic, Error Handling, API Tests

### Task 8: Update API Routes to Use Bookmark Service

**Files:**
- Modify: `app/api/routes/bookmarks.py`
- Modify: `app/api/routes/ingest.py`

- [ ] **Step 1: Rewrite bookmarks.py to use service layer**

Replace `app/api/routes/bookmarks.py` with:

```python
"""Bookmark list, discard, restore, and single-URL summary endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.status import BookmarkStatus, StatusFilter
from app.schemas.distill import BookmarkListResponse, BookmarkSchema, BriefItemSchema
from app.services.bookmark_service import (
    discard_bookmarks as svc_discard,
    get_bookmark_by_id,
    list_bookmarks as svc_list,
    move_bookmarks as svc_move,
    purge_bookmarks as svc_purge,
    restore_bookmarks as svc_restore,
)
from app.services.cache_service import get_cached_summary, update_cache
from app.services.distill_service import summarize_single

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    folder: str | None = None,
    category: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    include_discarded: bool = False,
    db: AsyncSession = Depends(get_db),
) -> BookmarkListResponse:
    """List stored bookmarks. Filter by folder, category, status."""
    if include_discarded:
        sf = StatusFilter.ALL
    else:
        try:
            sf = StatusFilter(status)
        except ValueError:
            sf = StatusFilter.ACTIVE
    items, total = await svc_list(
        db, category=category, folder=folder, status_filter=sf, limit=limit, offset=offset
    )
    return BookmarkListResponse(
        items=[BookmarkSchema.model_validate(b) for b in items],
        total=total,
    )


class BulkIdsRequest(BaseModel):
    """Request body for bulk operations."""
    ids: list[int]


class MoveToRequest(BaseModel):
    """Request to move bookmarks to preview or view."""
    ids: list[int]
    status: str  # "preview" | "view"


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_bookmark(
    bookmark_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a bookmark as discarded (soft delete)."""
    b = await get_bookmark_by_id(db, bookmark_id)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    await svc_discard(db, [bookmark_id])


@router.post("/discard-bulk", status_code=status.HTTP_200_OK)
async def discard_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Bulk soft-delete (discard) bookmarks by ID. Reversible via restore-bulk."""
    discarded = await svc_discard(db, body.ids)
    return {"discarded": len(discarded)}


@router.post("/purge-bulk", status_code=status.HTTP_200_OK)
async def purge_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Permanently delete soft-deleted bookmarks. Only purges items in discard status. Irreversible."""
    count = await svc_purge(db, body.ids)
    return {"purged": count}


@router.post("/restore-bulk", status_code=status.HTTP_200_OK)
async def restore_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Restore soft-deleted bookmarks from discard back to unreviewed."""
    restored = await svc_restore(db, body.ids)
    return {"restored": len(restored)}


@router.post("/move-bulk", status_code=status.HTTP_200_OK)
async def move_bookmarks_bulk(
    body: MoveToRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Move bookmarks to preview (AI fetch) or view (user's collection)."""
    try:
        target = BookmarkStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be 'preview' or 'view'",
        )
    if target not in (BookmarkStatus.PREVIEW, BookmarkStatus.VIEW):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be 'preview' or 'view'",
        )
    moved = await svc_move(db, body.ids, target)
    return {"moved": len(moved)}


class SummarizeRequest(BaseModel):
    """Request to summarize a single URL."""
    url: str


@router.post("/summarize", response_model=BriefItemSchema)
async def summarize_bookmark(
    body: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
) -> BriefItemSchema:
    """Fetch and summarize a single URL. Uses cache when available."""
    url = body.url
    if not url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http or https",
        )
    cached = await get_cached_summary(db, url)
    if cached:
        summary, key_points = cached
        item = await summarize_single(url, cached_summary=summary, cached_key_points=key_points)
    else:
        item = await summarize_single(url)
        await update_cache(db, url, item.summary, item.key_points)
    await db.commit()
    return BriefItemSchema.model_validate(item)
```

- [ ] **Step 2: Update ingest.py to use service for ingest**

In `app/api/routes/ingest.py`, replace the ingest endpoint's body to use the service:

Replace lines 25-57 with:

```python
@router.post("/ingest/bookmarks", response_model=IngestBookmarksResponse)
async def ingest_bookmarks(
    file: UploadFile,
    format: Literal["html", "json"] = "html",
    db: AsyncSession = Depends(get_db),
) -> IngestBookmarksResponse:
    """Accept HTML or JSON bookmark export, parse, and store."""
    from app.services.bookmark_service import ingest_bookmarks as svc_ingest

    content = (await file.read()).decode("utf-8", errors="replace")
    if format == "json":
        entries = list(parse_chrome_json(content))
    else:
        entries = list(parse_netscape_html(content))

    new_count, total = await svc_ingest(db, entries)
    return IngestBookmarksResponse(ingested=new_count, total=total)
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/api/routes/bookmarks.py app/api/routes/ingest.py
git commit -m "refactor: API routes now use bookmark_service for shared logic"
```

---

### Task 9: Error Handling Improvements

**Files:**
- Modify: `app/services/distill_service.py`
- Modify: `app/db/session.py`

- [ ] **Step 1: Add per-item error handling in distill_content**

In `app/services/distill_service.py`, replace the try/except block in `distill_content()` (lines 130-143) with:

```python
    try:
        brief: DistilledBrief = await client.create(  # type: ignore[misc]
            messages=[{"role": "user", "content": prompt}],
            response_model=DistilledBrief,
        )
        # Map back to original order
        idx_to_item = {indices[j]: brief.items[j] for j in range(len(brief.items))}
    except Exception as e:
        log.exception("distill_failed", error=str(e))
        # Create failure items for all text contents instead of crashing
        idx_to_item = {}
        for i, c in text_contents:
            idx_to_item[i] = BriefItem(
                title=c.title or c.url,
                url=c.url,
                summary="Failed to process",
                key_points=[],
                view=False,
            )

    for i, item in youtube_items:
        idx_to_item[i] = item
    ordered_items = [idx_to_item[i] for i in sorted(idx_to_item)]
    return DistilledBrief(items=ordered_items)
```

- [ ] **Step 2: Rename migration functions in session.py**

In `app/db/session.py`:

- Rename `_migrate_add_bookmark_status` to `_ensure_status_column` (line 52 definition, line 47 call)
- Rename `_migrate_add_group_and_cache` to `_ensure_category_and_cache_columns` (line 62 definition, line 48 call)
- Rename `_migrate_status_values` to `_normalize_legacy_status_values` (line 78 definition, line 49 call)

- [ ] **Step 3: Verify existing tests still pass**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/distill_service.py app/db/session.py
git commit -m "fix: per-item error handling in distill, rename migrations for clarity"
```

---

### Task 10: API Integration Tests

**Files:**
- Create: `tests/test_api_bookmarks.py`

- [ ] **Step 1: Write API integration tests**

Create `tests/test_api_bookmarks.py`:

```python
"""API integration tests for bookmark endpoints."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_html(client: AsyncClient) -> None:
    """Ingest HTML bookmark file via API."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://example.com">Example</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    r = await client.post("/ingest/bookmarks", files=files, data={"format": "html"})
    assert r.status_code == 200
    data = r.json()
    assert data["ingested"] == 1
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_bookmarks(client: AsyncClient) -> None:
    """List bookmarks after ingest."""
    # Ingest first
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://a.com">A</A><DT><A HREF="https://b.com">B</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_discard_and_restore_bulk(client: AsyncClient) -> None:
    """Discard and restore bookmarks via bulk endpoints."""
    # Ingest
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://c.com">C</A><DT><A HREF="https://d.com">D</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    # Get IDs
    r = await client.get("/bookmarks", params={"status": "active"})
    ids = [item["id"] for item in r.json()["items"]]

    # Discard
    r = await client.post("/bookmarks/discard-bulk", json={"ids": ids})
    assert r.status_code == 200
    assert r.json()["discarded"] == 2

    # Verify discarded
    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.json()["total"] == 0

    # Restore
    r = await client.post("/bookmarks/restore-bulk", json={"ids": ids})
    assert r.status_code == 200
    assert r.json()["restored"] == 2

    # Verify restored
    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_move_bulk(client: AsyncClient) -> None:
    """Move bookmarks to view status."""
    # Ingest
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://e.com">E</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    r = await client.get("/bookmarks", params={"status": "active"})
    ids = [item["id"] for item in r.json()["items"]]

    r = await client.post("/bookmarks/move-bulk", json={"ids": ids, "status": "view"})
    assert r.status_code == 200
    assert r.json()["moved"] == 1

    # Verify moved
    r = await client.get("/bookmarks", params={"status": "view"})
    assert r.json()["total"] == 1
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS (~22 tests total)

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_bookmarks.py
git commit -m "test: add API integration tests for bookmark endpoints"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `uv run ruff check .`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run type checking**

Run: `uv run pyright`
Expected: No errors (fix any that appear)

- [ ] **Step 4: Verify MCP server loads**

Run: `uv run python -c "from app.mcp.server import mcp; print('OK:', len(mcp._tool_manager._tools), 'tools')"`
Expected: `OK: <number> tools` (should be ~16 tools)

- [ ] **Step 5: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: fix lint and type check issues from foundation hardening"
```
