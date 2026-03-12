"""MCP tools: manage bookmark status (discard, move, purge, restore)."""

from sqlalchemy import select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.services import bookmark_service as svc


def register(mcp) -> None:  # type: ignore[type-arg]
    """Register management tools on the MCP instance."""

    @mcp.tool
    async def discard_bookmarks(bookmark_ids: list[int]) -> str:
        """Bulk discard bookmarks. Pass a list of IDs from list_bookmarks."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            discarded = await svc.discard_bookmarks(session, bookmark_ids)
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
            moved = await svc.move_bookmarks(session, bookmark_ids, BookmarkStatus.PREVIEW)
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
            moved = await svc.move_bookmarks(session, bookmark_ids, BookmarkStatus.VIEW)
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
                b = await svc.get_bookmark_by_id(session, bid)
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
            # Collect titles before purge for reporting
            titles: dict[int, str] = {}
            for bid in bookmark_ids:
                result = await session.execute(
                    select(Bookmark).where(
                        Bookmark.id == bid,
                        Bookmark.status == BookmarkStatus.DISCARD,
                    )
                )
                b = result.scalar_one_or_none()
                if b:
                    titles[bid] = b.title or ""
            purged_count = await svc.purge_bookmarks(session, bookmark_ids)
        if purged_count == 0:
            return "No discarded bookmarks found with those IDs. Only soft-deleted (discard) items can be purged."
        lines = [f"Purged {purged_count} bookmarks (permanently deleted):"]
        for bid, title in titles.items():
            lines.append(f"- {bid}: {title}")
        return "\n".join(lines)

    @mcp.tool
    async def restore_from_discard(bookmark_ids: list[int]) -> str:
        """Restore soft-deleted bookmarks from discard back to unreviewed. Reversible."""
        if not bookmark_ids:
            return "Provide at least one bookmark ID."
        async with async_session() as session:
            restored = await svc.restore_bookmarks(session, bookmark_ids)
        if not restored:
            return "No bookmarks found with those IDs."
        lines = [f"Restored {len(restored)} bookmarks to unreviewed:"]
        for b in restored:
            lines.append(f"- {b.id}: {b.title}")
        return "\n".join(lines)
