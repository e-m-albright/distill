# Distillation

Bookmark and content distillation — tame information overload.

## Quick Start

```bash
uv sync
cp .env.example .env
# Set GOOGLE_API_KEY in .env (get from https://aistudio.google.com/apikey)
just dev
```

## API

- `GET /health` — Health check (for n8n, deployment)
- `POST /ingest/bookmarks` — Upload bookmark export (HTML or JSON)
  - Form: `file` (file), `format` (html | json)
- `POST /distill` — Distill stored bookmarks into a brief
  - Query: `limit` (default 20)
- `GET /bookmarks` — List bookmarks (folder, limit, offset, include_discarded)
- `DELETE /bookmarks/{id}` — Discard a bookmark (soft delete)
- `POST /bookmarks/summarize` — Summarize a single URL (body: `{"url": "..."}`)

## Bookmark Export

- **Chrome**: Bookmarks → ⋮ → Export bookmarks (HTML)
- **Chrome JSON**: Copy from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`

## What's the DB for?

The SQLite database stores bookmarks between ingest and distill. You ingest once (upload your bookmark export), then can run distill multiple times without re-uploading. Without the DB, you'd need to pass bookmarks inline to distill every time.

## Claude Desktop (Interactive Chat)

**Quick install:**

```bash
./scripts/install-mcp.sh
```

Then restart Claude Desktop. See [docs/USAGE.md](docs/USAGE.md) for the full workflow (1500+ bookmarks, triage, summarize, discuss).

**Manual setup:** Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add the server (see `claude_desktop_config.json.example`). Or run:

```bash
uv run fastmcp install claude-desktop app/mcp_server.py:mcp --project . --name distillation --env-file .env
```

## Future Directions

- **n8n:** Webhook triggers, scheduled digests, ingest from email. See [docs/ROADMAP.md](docs/ROADMAP.md)
- **News/blogs/newsletters:** RSS feeds, configured sources, daily distillation

## Deployment

- **Standalone**: Run `uvicorn app.main:app` behind a reverse proxy
- **n8n**: Use HTTP Request node to call `POST /distill` or `POST /ingest/bookmarks`
