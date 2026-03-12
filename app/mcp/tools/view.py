"""MCP tools: view list of bookmarks to visit."""

import json

from fastmcp.server.apps import AppConfig
from sqlalchemy import select

from app.db.session import async_session
from app.mcp.constants import CSP, PERMS, VIEW_URI
from app.models.bookmark import Bookmark
from app.models.status import BookmarkStatus


def register(mcp) -> None:  # type: ignore[type-arg]
    """Register view tools on the MCP instance."""

    @mcp.tool(app=AppConfig(resource_uri=VIEW_URI, csp=CSP, permissions=PERMS))
    async def list_view(limit: int = 100) -> str:
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
