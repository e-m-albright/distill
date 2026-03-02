# Distillation

Bookmark and content distillation — tame information overload.

## Quick Start

```bash
uv sync
cp .env.example .env
# Set OPENAI_API_KEY in .env
just dev
```

## API

- `GET /health` — Health check (for n8n, deployment)
- `POST /ingest/bookmarks` — Upload bookmark export (HTML or JSON)
  - Form: `file` (file), `format` (html | json)
- `POST /distill` — Distill stored bookmarks into a brief
  - Query: `limit` (default 20)

## Bookmark Export

- **Chrome**: Bookmarks → ⋮ → Export bookmarks (HTML)
- **Chrome JSON**: Copy from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`

## Deployment

- **Standalone**: Run `uvicorn app.main:app` behind a reverse proxy
- **n8n**: Use HTTP Request node to call `POST /distill` or `POST /ingest/bookmarks`
