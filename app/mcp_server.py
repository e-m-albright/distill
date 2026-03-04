"""MCP server for Claude Desktop — interactive bookmark distillation."""

import asyncio
import json
import logging
import sys
from datetime import UTC
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig, ResourceCSP, ResourcePermissions


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
from sqlalchemy import func, or_, select

from app.db.session import async_session, init_db
from app.models.bookmark import Bookmark
from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html
from app.services.cache_service import get_cached_summary, update_cache
from app.services.content_fetcher import ExtractedContent, fetch_and_extract
from app.services.distill_service import distill_content, summarize_single
from app.services.organize_service import organize_bookmarks as organize_service


# Path to mcp-app HTML files (project root / mcp-app)
_MCP_APP_DIR = Path(__file__).resolve().parent.parent / "mcp-app"
_TRIAGE_URI = "ui://distillation/triage.html"
_PREVIEW_URI = "ui://distillation/preview.html"
_VIEW_URI = "ui://distillation/view.html"
_CSP = ResourceCSP(resource_domains=["https://unpkg.com"])
_PERMS = ResourcePermissions(clipboard_write={})


def _load_html(name: str) -> str:
    path = _MCP_APP_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


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

    ingested = 0
    async with async_session() as session:
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
                        status="unreviewed",
                    )
                )
                ingested += 1
        await session.commit()
    return f"Ingested {ingested} new bookmarks from {len(entries)} total in file."


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
                Bookmark.status == "unreviewed",
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
                Bookmark.status == "unreviewed",
                or_(Bookmark.category == "", Bookmark.category.is_(None)),
            )
        ) or 0
    lines = [f"Organized {len(assignments)} bookmarks into {len(categories)} groups:"]
    for c in categories:
        lines.append(f"- {c}: {counts.get(c, 0)}")
    lines.append(f"\nUnorganized remaining: {remaining}. Run again to process more." if remaining else "\nAll bookmarks organized.")
    return "\n".join(lines)


@mcp.tool
async def list_groups() -> str:
    """List bookmark category counts. Shows TOTAL, ORGANIZED, and UNORGANIZED so you know the full picture.
    Groups = organized only. Unorganized bookmarks have no category yet — run organize_bookmarks to assign them (500 per run)."""
    async with async_session() as session:
        total = await session.scalar(
            select(func.count()).select_from(Bookmark).where(
                Bookmark.status.in_(["unreviewed", "preview", "view"])
            )
        ) or 0
        unorg = await session.scalar(
            select(func.count())
            .select_from(Bookmark)
            .where(
                Bookmark.status.in_(["unreviewed", "preview", "view"]),
                or_(Bookmark.category == "", Bookmark.category.is_(None)),
            )
        ) or 0
        result = await session.execute(
            select(Bookmark.category, func.count())
            .where(
                Bookmark.status.in_(["unreviewed", "preview", "view"]),
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
                Bookmark.status.in_(["discard", "discarded"])
            )
        ) or 0
        view_count = await session.scalar(
            select(func.count()).select_from(Bookmark).where(Bookmark.status == "view")
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


# Valid status values (strict). Used for validation and filtering.
VALID_STATUSES = frozenset({"unreviewed", "preview", "view", "discard", "active", "discarded"})


def _status_filter(status: str) -> list[Any]:
    """Resolve status to SQL filter.
    active = unreviewed only (organized, not yet moved to preview/view).
    kept = all non-discard (unreviewed + preview + view).
    discard/discarded = soft-deleted (handles legacy)."""
    if status == "all":
        return []
    if status == "active":
        return [Bookmark.status.in_(["unreviewed", "active"])]
    if status == "kept":
        return [Bookmark.status.in_(["unreviewed", "preview", "view", "active"])]
    if status in ("discard", "discarded"):
        return [Bookmark.status.in_(["discard", "discarded"])]
    if status in VALID_STATUSES:
        return [Bookmark.status == status]
    return [Bookmark.status == status]


@mcp.tool
async def list_by_status(
    status_filter: str = "all",
    limit: int = 500,
) -> str:
    """Debug: List ALL bookmarks by status across all categories. Shows id, status, category, title, url.
    status_filter: active, kept, unreviewed, preview, view, discard, all.
    Use to verify distribution and find missing bookmarks."""
    status_where = _status_filter(status_filter)
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
    status_filter = _status_filter(status)
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


@mcp.tool(app=AppConfig(resource_uri=_TRIAGE_URI, csp=_CSP, permissions=_PERMS))
async def triage(
    category: str | None = None,
    folder: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Show triage UI: list bookmarks by title/URL for review. Same filters as list_bookmarks."""
    status_filter = _status_filter(status)
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


@mcp.resource(_TRIAGE_URI, app=AppConfig(csp=_CSP, permissions=_PERMS))
def triage_view() -> str:
    """Triage UI resource."""
    return _load_html("triage.html")


@mcp.tool(app=AppConfig(resource_uri=_PREVIEW_URI, csp=_CSP, permissions=_PERMS))
async def preview(
    limit: int = 20,
    category: str | None = None,
    folder: str | None = None,
    use_cache: bool = True,
) -> str:
    """Run preview: fetch and summarize each link (per-link, no overview). Filter by category or folder.
    Confirm with user which links to preview before running. Cached summaries reused when use_cache=True."""
    cat_filter = [Bookmark.category == category] if category else []
    folder_filter = [Bookmark.folder == folder] if folder else []
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark)
            .where(
                Bookmark.status.in_(["unreviewed", "preview"]),
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
            from datetime import datetime, timedelta

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


@mcp.resource(_PREVIEW_URI, app=AppConfig(csp=_CSP, permissions=_PERMS))
def preview_view() -> str:
    """Preview UI resource (post-preview)."""
    return _load_html("preview.html")


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


@mcp.tool
async def discard_bookmarks(bookmark_ids: list[int]) -> str:
    """Bulk discard bookmarks. Pass a list of IDs from list_bookmarks."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID."
    async with async_session() as session:
        discarded: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
            if b:
                b.status = "discard"
                discarded.append((bid, b.title))
        await session.commit()
    if not discarded:
        return "No bookmarks found with those IDs."
    lines = [f"Discarded {len(discarded)} bookmarks:"]
    for bid, title in discarded:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def move_to_preview(bookmark_ids: list[int]) -> str:
    """Move bookmarks to preview status (for AI fetch/summarize). Only when user confirms."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID."
    async with async_session() as session:
        moved: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
            if b:
                b.status = "preview"
                moved.append((bid, b.title))
        await session.commit()
    if not moved:
        return "No bookmarks found with those IDs."
    lines = [f"Moved {len(moved)} bookmarks to preview:"]
    for bid, title in moved:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def move_to_view(bookmark_ids: list[int]) -> str:
    """Move bookmarks to view status (user's collection to visit). Only when user confirms."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID."
    async with async_session() as session:
        moved: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
            if b:
                b.status = "view"
                moved.append((bid, b.title))
        await session.commit()
    if not moved:
        return "No bookmarks found with those IDs."
    lines = [f"Moved {len(moved)} bookmarks to view:"]
    for bid, title in moved:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool(app=AppConfig(resource_uri=_VIEW_URI, csp=_CSP, permissions=_PERMS))
async def list_view(
    limit: int = 100,
) -> str:
    """Show View UI: links in your collection to visit. Run to display the view list."""
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark)
            .where(Bookmark.status == "view")
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


@mcp.resource(_VIEW_URI, app=AppConfig(csp=_CSP, permissions=_PERMS))
def view_view() -> str:
    """View UI resource (links to visit)."""
    return _load_html("view.html")


@mcp.tool
async def suggest_discard(bookmark_ids: list[int]) -> str:
    """Present these bookmark IDs as suggested discards. Does NOT discard—format for user to review.
    Only call discard_bookmarks when user explicitly confirms."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID to suggest for discard."
    async with async_session() as session:
        items: list[tuple[int, str, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
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
        purged: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(
                select(Bookmark).where(
                    Bookmark.id == bid,
                    Bookmark.status.in_(["discard", "discarded"]),
                )
            )
            b = result.scalar_one_or_none()
            if b:
                session.delete(b)
                purged.append((bid, b.title))
        await session.commit()
    if not purged:
        return "No discarded bookmarks found with those IDs. Only soft-deleted (discard) items can be purged."
    lines = [f"Purged {len(purged)} bookmarks (permanently deleted):"]
    for bid, title in purged:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def restore_from_discard(bookmark_ids: list[int]) -> str:
    """Restore soft-deleted bookmarks from discard back to unreviewed. Reversible."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID."
    async with async_session() as session:
        restored: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
            if b:
                b.status = "unreviewed"
                restored.append((bid, b.title))
        await session.commit()
    if not restored:
        return "No bookmarks found with those IDs."
    lines = [f"Restored {len(restored)} bookmarks to unreviewed:"]
    for bid, title in restored:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def discard_bookmark(bookmark_id: int) -> str:
    """Mark a single bookmark as discard. For bulk, use discard_bookmarks. Only when user confirms."""
    async with async_session() as session:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            return f"Bookmark {bookmark_id} not found."
        bookmark.status = "discard"
        await session.commit()
    return f"Discarded bookmark {bookmark_id}: {bookmark.title}"


def main() -> None:
    import asyncio

    asyncio.run(init_db())
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
