"""MCP tool: ingest bookmarks from file."""

from pathlib import Path

from fastmcp import FastMCP

from app.db.session import async_session
from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html
from app.services.bookmark_service import ingest_bookmarks as svc_ingest


def register(mcp: FastMCP) -> None:
    """Register ingest tools on the MCP instance."""

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
