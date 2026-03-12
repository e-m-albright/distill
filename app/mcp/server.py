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

from app.mcp.tools import ingest, manage, organize, preview, triage, view  # noqa: E402


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
    await mcp.run_async(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
