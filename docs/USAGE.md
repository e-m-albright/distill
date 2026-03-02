# Distillation Usage Guide

## How the MCP Server Gets Your Bookmarks

**You give Claude the file path.** When you say "ingest my bookmarks from ~/Downloads/bookmarks.html", Claude calls the `ingest_bookmarks` tool with that path. The MCP server reads the file from your filesystem and parses it. No upload—Claude passes the path you provide.

**Export first:** In Chrome, go to Bookmarks → ⋮ → Export bookmarks. Save as HTML (or use Chrome JSON from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`).

---

## Workflow: Ingest → Organize → Triage → Promote → Distill

### 1. Ingest

```
"Ingest my bookmarks from ~/Downloads/bookmarks.html"
```

### 2. Organize (Assign Groups)

Define categories and let AI assign each bookmark:

```
"Organize my bookmarks into: low_value, high_value, AI, cooking, parenting, work, news"
```

AI assigns based on title, URL, and folder. You can now work through one group at a time.

### 3. Pick a Group

```
"List my groups"
"List bookmarks in category 'cooking', limit 50"
```

### 4. Summarize the Group (Triage)

```
"Distill the cooking bookmarks, limit 30"
```

Each item gets: summary, key points, keep/discard suggestion. **Summaries are cached**—re-running uses cache, no re-fetch or tokens.

### 5. Bulk Discard Low-Value

```
"Discard bookmarks 15, 23, 31, 42"
```

### 6. Promote Survivors (Deeper Review)

```
"Promote bookmarks 7, 12, 19"
```

Promoted items move to `status=promoted` for later deeper review.

### 7. Distill Key Learnings (Promoted Items)

```
"List bookmarks with status promoted"
"Summarize https://..."  (uses cache if already summarized)
```

### 8. Continue or Switch Groups

Pick up where you left off—organization and status persist. Switch groups anytime:

```
"Let's work on the AI group"
"List bookmarks in category AI"
"Distill category AI, limit 20"
```

---

## Caching (Save Time & Tokens)

- **Distill** — Summaries and key points are stored per bookmark. Re-distilling uses cache (30-day TTL).
- **Summarize** — Single-URL summaries are cached. Re-requesting returns cached result.
- **Organize** — No fetch; uses title/URL/folder only (cheap).

---

## URL Visibility

- **Bulk (list_bookmarks):** `[title](url)` — click to open
- **Bulk (distill):** `[title](url)` — click to open
- **Singular (summarize_bookmark):** `[title](url)` — click to open

---

## Tools Reference

| Tool | Purpose |
|------|---------|
| `ingest_bookmarks` | Ingest from file path |
| `organize_bookmarks` | Assign categories (AI-driven) |
| `list_groups` | See category counts |
| `list_folders` | See browser folder structure |
| `list_bookmarks` | List with category/folder/status filter |
| `distill` | Batch summarize (uses cache) |
| `summarize_bookmark` | Single URL (uses cache) |
| `discard_bookmarks` | Bulk discard by IDs |
| `promote_bookmarks` | Mark for deeper review |
| `discard_bookmark` | Single discard |
