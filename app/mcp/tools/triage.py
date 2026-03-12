"""MCP tools: triage bookmarks."""

import json
from typing import Any

from fastmcp.server.apps import AppConfig
from sqlalchemy import func, select

from app.db.session import async_session
from app.mcp.constants import CSP, PERMS, TRIAGE_URI
from app.models.bookmark import Bookmark
from app.models.status import StatusFilter, resolve_status_filter


def _build_status_filter(status: str) -> list[Any]:
    """Resolve a status string to SQLAlchemy WHERE conditions."""
    try:
        sf = StatusFilter(status)
    except ValueError:
        # Fall back to direct equality for unknown values
        return [Bookmark.status == status]
    resolved = resolve_status_filter(sf)
    if resolved is None:
        return []
    if len(resolved) == 1:
        return [Bookmark.status == resolved[0]]
    return [Bookmark.status.in_([s.value for s in resolved])]


def register(mcp) -> None:  # type: ignore[type-arg]
    """Register triage tools on the MCP instance."""

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
        status_filter = _build_status_filter(status)
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
        async with async_session() as session:
            result = await session.execute(
                select(Bookmark.folder)
                .where(
                    Bookmark.status.in_(["unreviewed", "preview", "view"]),
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
        status_filter = _build_status_filter(status)
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
        status_where = _build_status_filter(status_filter)
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
            unreviewed_result = await session.execute(
                select(func.count()).select_from(Bookmark).where(
                    Bookmark.status.in_(["unreviewed", "active"])
                )
            )
            unreviewed = unreviewed_result.scalar() or 0
            preview_result = await session.execute(
                select(func.count()).select_from(Bookmark).where(Bookmark.status == "preview")
            )
            preview = preview_result.scalar() or 0
            view_result = await session.execute(
                select(func.count()).select_from(Bookmark).where(Bookmark.status == "view")
            )
            view = view_result.scalar() or 0
            discard_result = await session.execute(
                select(func.count()).select_from(Bookmark).where(
                    Bookmark.status.in_(["discard", "discarded"])
                )
            )
            discard = discard_result.scalar() or 0

        summed = unreviewed + preview + view + discard
        other = total - summed

        lines = [
            "Status summary (reconciliation report):",
            "",
            f"  total:     {total}",
            f"  active:    {unreviewed}  (unreviewed/organized, not yet moved)",
            f"  preview:   {preview}",
            f"  view:      {view}",
            f"  discard:   {discard}",
            "",
            f"  sum:       {summed}",
        ]
        if other != 0:
            lines.append(f"  other:     {other}  (unexpected status values)")
        if total != summed + other:
            lines.append(f"  WARNING: sum ({summed}) != total ({total})")
        return "\n".join(lines)
