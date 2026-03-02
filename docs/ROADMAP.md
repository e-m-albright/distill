# Distillation Roadmap

## Current (Phase 1)

- [x] Bookmark export ingest (HTML/JSON)
- [x] Direct distill to brief
- [x] MCP + Claude Desktop interactive chat
- [x] List, discard, single-URL summarize
- [x] Standalone HTTP API
- [x] n8n HTTP Request support

---

## Phase 2: n8n Integration

**Goal:** Trigger distillation from n8n workflows.

### Planned

1. **Webhook endpoint** — `POST /webhook/distill` with optional bookmark URLs or "use stored"
2. **Scheduled distill** — n8n Cron node → HTTP Request → distill → output to Slack/email/Notion
3. **Ingest from n8n** — Webhook accepts bookmark JSON/HTML in body (no file upload)
4. **Return format** — Structured JSON for n8n to parse and route

### n8n Use Cases

- Daily digest: Cron at 8am → distill last 24h of ingested content → Slack
- Newsletter trigger: Email node → extract links → ingest → distill
- Manual trigger: Button → distill → send to user

---

## Phase 3: News, Blogs, Newsletters

**Goal:** Ingest from configured sources, not just bookmark exports.

### News / Blogs / Thought Pieces

1. **RSS/Atom feeds** — OPML or config file listing feeds
2. **Scheduled fetch** — Cron pulls new items, stores as "bookmarks" with source metadata
3. **Filter by source** — Distill only from certain feeds (e.g. "tech news", "personal blogs")

### Newsletters

1. **Email ingest** — IMAP or n8n Email node → extract links + body → store
2. **n8n webhook** — Forward newsletter to webhook; extract content
3. **RSS of newsletters** — Many newsletters have RSS; treat as feed

### Format

- New model: `ContentSource` (type: bookmark | rss | newsletter)
- Bookmarks stay as-is; RSS/newsletter items get `source` and `fetched_at`

---

## Phase 4: Daily Distillation

**Goal:** A manageable daily digest of the constant stream.

### Vision

1. **Unified inbox** — Bookmarks + RSS + newsletters in one pool
2. **Daily run** — Cron (or n8n) runs distill on "new since last run"
3. **Priority scoring** — Optional: LLM or rules to rank items (source reputation, recency, user history)
4. **Digest format** — Overview + top N items + "rest in brief" link
5. **Delivery** — Slack, email, or in-app view

### Technical Path

- Add `last_distilled_at` or `ingested_at` for filtering "new"
- Batch by day; cap tokens per run
- Optional: cache summaries to avoid re-fetching on re-distill

---

## Open Questions

- **RSS format:** OPML import vs. YAML/JSON config?
- **Newsletter auth:** OAuth for Gmail/Outlook vs. app passwords?
- **n8n vs. standalone cron:** Prefer n8n for flexibility or built-in scheduler?
- **Daily digest UI:** Email template? Slack blocks? Simple HTML?
