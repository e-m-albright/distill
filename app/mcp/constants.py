"""Shared MCP constants. Imported by server.py and tool modules to avoid circular imports."""

from pathlib import Path

from fastmcp.server.apps import ResourceCSP, ResourcePermissions


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
