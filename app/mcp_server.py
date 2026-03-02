"""MCP server for Claude Desktop — interactive bookmark distillation."""

import asyncio
from datetime import UTC
from pathlib import Path

from fastmcp import FastMCP
from sqlalchemy import func, select

from app.db.session import async_session, init_db
from app.models.bookmark import Bookmark
from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html
from app.services.cache_service import get_cached_summary, update_cache
from app.services.content_fetcher import ExtractedContent, fetch_and_extract
from app.services.distill_service import distill_content, summarize_single
from app.services.organize_service import organize_bookmarks as organize_service


mcp = FastMCP(
    name="Distillation",
    instructions="""You help the user chew through their bookmarks and tame information overload.

Workflow: Ingest → Organize (into groups) → Summarize groups → Pick a group → Bulk discard → Promote survivors → Distill key learnings → Continue.

Use organize_bookmarks first to assign categories (low_value, high_value, AI, cooking, parenting, etc.). Work through one group at a time. Use discard_bookmarks to bulk discard. Use promote_bookmarks to mark items for deeper review. Summaries and key points are cached—no redundant fetches.

Always show URLs as markdown links [title](url). Guide the user through the workflow.""",
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
                        status="active",
                    )
                )
                ingested += 1
        await session.commit()
    return f"Ingested {ingested} new bookmarks from {len(entries)} total in file."


@mcp.tool
async def organize_bookmarks(categories: list[str]) -> str:
    """Assign all active bookmarks to user-defined groups. Categories are labels like: low_value, high_value, AI, cooking, parenting, work, news, etc.
    AI assigns each bookmark to one category based on title, URL, and folder. Run this after ingest to work through groups one at a time."""
    if len(categories) < 2:
        return "Provide at least 2 categories, e.g. ['low_value', 'high_value', 'AI', 'cooking']"
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark).where(Bookmark.status == "active").limit(500)
        )
        bookmarks = result.scalars().all()
    if not bookmarks:
        return "No active bookmarks. Ingest first."
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
    lines = [f"Organized {len(assignments)} bookmarks into {len(categories)} groups:"]
    for c in categories:
        lines.append(f"- {c}: {counts.get(c, 0)}")
    return "\n".join(lines)


@mcp.tool
async def list_groups() -> str:
    """List all bookmark categories (from organize_bookmarks). Use to pick a group to work on."""
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark.category, func.count())
            .where(
                Bookmark.status.in_(["active", "promoted"]),
                Bookmark.category != "",
            )
            .group_by(Bookmark.category)
            .order_by(Bookmark.category)
        )
        rows = result.fetchall()
    if not rows:
        return "No groups yet. Run organize_bookmarks first with your categories."
    return "Groups:\n" + "\n".join(f"- {cat}: {n}" for cat, n in rows)


@mcp.tool
async def list_folders() -> str:
    """List all bookmark folder paths (from browser export). Use to see structure before organizing."""
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark.folder)
            .where(Bookmark.status == "active", Bookmark.folder != "")
            .distinct()
            .order_by(Bookmark.folder)
        )
        folders = [r[0] for r in result.fetchall()]
    if not folders:
        return "No folders found (bookmarks may be in root). Use list_bookmarks to see all."
    return "Folders:\n" + "\n".join(f"- {f}" for f in folders)


@mcp.tool
async def list_bookmarks(
    category: str | None = None,
    folder: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List stored bookmarks. Filter by category (from organize), folder (from export), or status (active|promoted|discarded).
    Use category to work through one group at a time."""
    status_filter = []
    if status != "all":
        status_filter = [Bookmark.status == status]
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
        f"Total: {total} | Showing {len(items)} (IDs for discard_bookmarks, promote_bookmarks)"
    ]
    for b in items:
        cat = f" | {b.category}" if b.category else ""
        lines.append(f"- [{b.id}] [{b.title}]({b.url}){cat}")
    return "\n".join(lines)


@mcp.tool
async def distill(
    limit: int = 20,
    category: str | None = None,
    folder: str | None = None,
    use_cache: bool = True,
) -> str:
    """Run batch distillation. Fetches content (or uses cached summary), summarizes each, returns brief with keep/discard suggestions.
    Filter by category or folder to work through one group. Cached summaries are reused (use_cache=True) to save time and tokens."""
    cat_filter = [Bookmark.category == category] if category else []
    folder_filter = [Bookmark.folder == folder] if folder else []
    async with async_session() as session:
        result = await session.execute(
            select(Bookmark)
            .where(Bookmark.status == "active", *cat_filter, *folder_filter)
            .limit(limit)
        )
        bookmarks = result.scalars().all()

    if not bookmarks:
        return "No active bookmarks to distill. Ingest and organize first."

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

    lines = [f"## Overview\n{brief.overview}\n", f"Discarded: {brief.discarded_count}\n"]
    for i in brief.items:
        keep = "✓ keep" if i.keep else "✗ discard"
        pts = "\n  - " + "\n  - ".join(i.key_points) if i.key_points else ""
        lines.append(f"### [{i.title}]({i.url})\n- {keep}\n- Summary: {i.summary}{pts}\n")
    return "\n".join(lines)


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
                b.status = "discarded"
                discarded.append((bid, b.title))
        await session.commit()
    if not discarded:
        return "No bookmarks found with those IDs."
    lines = [f"Discarded {len(discarded)} bookmarks:"]
    for bid, title in discarded:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def promote_bookmarks(bookmark_ids: list[int]) -> str:
    """Mark bookmarks for deeper review (survive to next round). Use after triage to keep high-value items."""
    if not bookmark_ids:
        return "Provide at least one bookmark ID."
    async with async_session() as session:
        promoted: list[tuple[int, str]] = []
        for bid in bookmark_ids:
            result = await session.execute(select(Bookmark).where(Bookmark.id == bid))
            b = result.scalar_one_or_none()
            if b:
                b.status = "promoted"
                promoted.append((bid, b.title))
        await session.commit()
    if not promoted:
        return "No bookmarks found with those IDs."
    lines = [f"Promoted {len(promoted)} bookmarks for deeper review:"]
    for bid, title in promoted:
        lines.append(f"- {bid}: {title}")
    return "\n".join(lines)


@mcp.tool
async def discard_bookmark(bookmark_id: int) -> str:
    """Mark a single bookmark as discarded. For bulk, use discard_bookmarks."""
    async with async_session() as session:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            return f"Bookmark {bookmark_id} not found."
        bookmark.status = "discarded"
        await session.commit()
    return f"Discarded bookmark {bookmark_id}: {bookmark.title}"


def main() -> None:
    import asyncio

    asyncio.run(init_db())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
