"""Backwards-compatible entry point. Delegates to app.mcp.server."""

from app.mcp.server import main, mcp


__all__ = ["main", "mcp"]

if __name__ == "__main__":
    main()
