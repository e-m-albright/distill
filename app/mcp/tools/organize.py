"""MCP tools: organize and group bookmarks."""

from sqlalchemy import func, or_, select

from app.db.session import async_session
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus
from app.services.organize_service import organize_bookmarks as organize_service


def register(mcp) -> None:  # type: ignore[type-arg]
    """Register organize tools on the MCP instance."""

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
