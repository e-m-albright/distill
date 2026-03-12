"""MCP tools: preview and summarize bookmarks."""

import asyncio
import json
from datetime import UTC

from fastmcp.server.apps import AppConfig
from sqlalchemy import select

from app.db.session import async_session
from app.mcp.constants import CSP, PERMS, PREVIEW_URI
from app.models.bookmark import Bookmark
from app.services.cache_service import get_cached_summary, update_cache
from app.services.content_fetcher import ExtractedContent, fetch_and_extract
from app.services.distill_service import distill_content, summarize_single


def register(mcp) -> None:  # type: ignore[type-arg]
    """Register preview tools on the MCP instance."""

    @mcp.tool(app=AppConfig(resource_uri=PREVIEW_URI, csp=CSP, permissions=PERMS))
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
