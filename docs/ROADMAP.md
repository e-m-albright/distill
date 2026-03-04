# Distillation Roadmap

## Current (Phase 1)

- [x] Bookmark export ingest (HTML/JSON)
- [x] Direct distill/preview to brief (per-link)
- [x] MCP + Claude Desktop interactive chat
- [x] List, discard, single-URL summarize
- [x] Standalone HTTP API
- [x] n8n HTTP Request support
- [x] Jina Reader for Reddit, paywalls, JS-heavy sites
- [x] Gemini native YouTube video summarization
- [x] Status model: unreviewed, discard, preview, view
- [x] Triage UI, Preview UI, View UI
- [x] No auto-discard; suggest_discard for confirmation flow

---

## Next Up: Backlog Experience Improvements

**Goal:** Make processing hundreds/thousands of bookmarks feel manageable and delightful.

### High Impact

- [ ] **write_artifact** — Tool to produce digest/learning notes from summarized links
- [ ] **Progress & milestones** — "234 of 1,847 processed", "25% done"
- [ ] **Bulk discard by pattern** — "Discard all Google Search" or "Discard all from domain X"
- [ ] **Streaming preview** — Show summaries as they complete, not all at once
- [ ] **Keyboard shortcuts** — j/k navigation, number keys for discard/view in UIs
- [ ] **Daily digest** — "5 from your backlog worth your time today"

### Quick Wins

- [ ] **Dark mode** — CSS variables for theme toggle
- [ ] **Retry button** — On failed preview items
- [ ] **Copy all view URLs** — One action to copy the whole view list
- [ ] **Estimated reading time** — Per item (from summary length or metadata)
- [ ] **Toast feedback** — Clear success on discard/view actions

### Workflow & Progress

- [ ] **Estimated time** — "~2 min per item → ~3 hours remaining"
- [ ] **Resumable sessions** — "Continue where you left off"
- [ ] **Smart batching** — "Process 20 now" or "Quick 5" suggestions

### Claude Integration

- [ ] **Proactive suggestions** — "Want me to suggest discards based on patterns?"
- [ ] **Natural language filters** — "Most actionable from AI" or "Most interesting in cooking"
- [ ] **Context/memory** — Remember interests and past choices

### UI Polish

- [ ] **Skeleton loading** — Instead of blank screens
- [ ] **Group-by** — By domain, type, or category for faster scanning
- [ ] **Infinite scroll / virtual list** — Handle thousands of items
- [ ] **Subtle animations** — When items are discarded or moved

### Content & Extraction

- [ ] **Duplicate detection** — "These 3 links might be the same article"
- [ ] **Pre-fetch during triage** — Start fetching visible items so preview is instant
- [ ] **Retry failed fetches** — One-click retry for failed previews

### Magic Moments

- [ ] **Quick wins** — "3 under 2 min read — knock them out"
- [ ] **Deep dives** — "These 3 deserve 15+ min each"
- [ ] **"I'm bored"** — Random high-value item from view collection
- [ ] **Export** — Send view collection to Notion, Readwise, or reading list

---

## Phase 2: n8n Integration

**Goal:** Trigger distillation from n8n workflows.

### Planned

1. **Webhook endpoint** — `POST /webhook/preview` with optional bookmark URLs or "use stored"
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

## Recommended Next

**Priority order for the backlog:**

1. **write_artifact** — Unlocks "write what I learned" from summarized links. High value, clear scope.
2. **Progress & milestones** — Makes large backlogs feel tractable. Simple to add (counts, percentages).
3. **Bulk discard by pattern** — "Discard all Google Search" or by domain. Saves tons of manual triage.
4. **Streaming preview** — Better UX; requires async refactor of preview flow.
5. **Keyboard shortcuts** — j/k, numbers for power users. Quick win in UI.

**Defer:** Phase 2 (n8n) and Phase 3 (RSS) until the core backlog experience is solid. The daily digest and export ideas can overlap with Phase 4.

---

## Open Questions

- **RSS format:** OPML import vs. YAML/JSON config?
- **Newsletter auth:** OAuth for Gmail/Outlook vs. app passwords?
- **n8n vs. standalone cron:** Prefer n8n for flexibility or built-in scheduler?
- **Daily digest UI:** Email template? Slack blocks? Simple HTML?
