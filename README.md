# Distillation

Bookmark and content distillation — tame information overload. Ingest exports, organize into categories, triage, preview (AI summarize), and curate a view collection.

## Quick Start

```bash
uv sync
cp .env.example .env
# Set GOOGLE_API_KEY in .env (get from https://aistudio.google.com/apikey)
# Optional: JINA_API_KEY for higher rate limits on content fetch
just dev
```

## API

- `GET /health` — Health check (for n8n, deployment)
- `POST /ingest/bookmarks` — Upload bookmark export (HTML or JSON)
  - Form: `file` (file), `format` (html | json)
- `POST /preview` — Fetch and summarize stored bookmarks (per-link)
  - Query: `limit` (default 20)
- `POST /distill` — Alias for `/preview` (backwards compat)
- `GET /bookmarks` — List bookmarks (folder, category, status, limit, offset)
  - Status: `active` (unreviewed), `kept` (all non-discard), `discard`, `preview`, `view`, `all`
- `DELETE /bookmarks/{id}` — Soft-delete (discard) a bookmark
- `POST /bookmarks/discard-bulk` — Bulk discard (body: `{"ids": [...]}`)
- `POST /bookmarks/restore-bulk` — Restore from discard (body: `{"ids": [...]}`)
- `POST /bookmarks/purge-bulk` — Permanently delete discarded bookmarks (body: `{"ids": [...]}`)
- `POST /bookmarks/move-bulk` — Move to preview or view (body: `{"ids": [...], "status": "preview"|"view"}`)
- `POST /bookmarks/summarize` — Summarize a single URL (body: `{"url": "..."}`)

## Content Fetching

- **Jina Reader** — Primary fetcher for Reddit, paywalls, JS-heavy sites. Optional `JINA_API_KEY` for higher rate limits.
- **Gemini** — Native YouTube video summarization (no HTML fetch).
- **httpx** — Fallback for simple pages.

## What's the DB for?

The SQLite database stores bookmarks between ingest and distill. You ingest once (upload your bookmark export), then can triage, preview, and curate without re-uploading.

## Bookmark Export

- **Chrome**: Bookmarks → ⋮ → Export bookmarks (HTML)
- **Chrome JSON**: Copy from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`

## Status Model

| Status      | Meaning                                      |
|-------------|----------------------------------------------|
| `unreviewed`| Default. Not yet triaged.                    |
| `active`    | Alias for unreviewed (organized, not moved). |
| `preview`   | AI fetch/summarize. Awaiting user review.    |
| `view`      | User's curated collection to visit.          |
| `discard`   | Soft-deleted. Reversible via restore.       |

## Claude Desktop (MCP)

**Quick install:**

```bash
./scripts/install-mcp.sh
```

Then restart Claude Desktop. See [docs/USAGE.md](docs/USAGE.md) for the full workflow (ingest → organize → triage → preview → view).

**Manual setup:** Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add the server (see `claude_desktop_config.json.example`). Or run:

```bash
uv run fastmcp install claude-desktop app/mcp_server.py:mcp --project . --name distillation --env-file .env
```

**Key tools:** `ingest_bookmarks`, `organize_bookmarks`, `list_groups`, `triage`, `preview`, `list_view`, `discard_bookmarks`, `restore_from_discard`, `purge_bookmarks`, `get_status_summary`, `reconcile_status`

## Future Directions

- **n8n:** Webhook triggers, scheduled digests, ingest from email. See [docs/ROADMAP.md](docs/ROADMAP.md)
- **News/blogs/newsletters:** RSS feeds, configured sources, daily distillation

## Deployment

- **Standalone**: Run `uvicorn app.main:app` behind a reverse proxy
- **n8n**: Use HTTP Request node to call `POST /preview` or `POST /ingest/bookmarks`
