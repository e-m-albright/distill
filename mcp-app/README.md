# MCP App: Bookmark Review UIs

Two UIs for the bookmark workflow:

| UI | When | Data source |
|----|------|-------------|
| **quick-pass.jsx** | Quick discard pass (before distill) | `list_bookmarks` |
| **bookmark-review.jsx** | Deep review (after distill) | `distill` |

## Quick Pass UI (`quick-pass.jsx`)

Title/URL-only review for discarding obvious junk before running distill. Matches the Downloads example:

- **Type badges** inferred from URL (Google Search, YouTube Short, Checkout/Cart, Untitled, etc.)
- **Filter tabs** by type with counts
- **Select all in view**
- **Confirm discard** (copies IDs to clipboard or calls `onDiscard`)

Data shape: `{ items: [{ id, title, url }], category?: string }` — matches `list_bookmarks` output.

---

## Bookmark Review UI (`bookmark-review.jsx`)

Post-distill UI for bulk triage (discard / promote). Designed to receive data from the `distill` tool and call `discard_bookmarks` / `promote_bookmarks` via MCP.

## Improvements over Claude's version

| Aspect | Claude's version | This version |
|--------|------------------|--------------|
| **Data** | Hardcoded `type` + `label` only | Uses `BriefItem` shape: summary, key_points, keep |
| **Summary** | Not shown | Primary content — the whole point of distillation |
| **Key points** | Not shown | Bulleted list under summary |
| **AI suggestion** | Implicit in filter | Explicit Keep/Discard badge per item |
| **Actions** | Discard only | Discard + Promote for deeper review |
| **Filter** | By type (Google Search, etc.) | By AI suggestion (all / discard / keep) |
| **Design** | Generic gray (#f9fafb, #6b7280) | Warm editorial (#f7f5f2, stone palette) |
| **MCP-ready** | Copy IDs to clipboard | `onDiscard`, `onPromote` callbacks for `callServerTool` |

## Data shape (from distill tool)

```json
{
  "overview": "2-3 sentence synthesis...",
  "items": [
    {
      "id": 387,
      "title": "plato books",
      "url": "https://...",
      "summary": "1-2 sentence summary",
      "key_points": ["point 1", "point 2"],
      "keep": false
    }
  ],
  "discarded_count": 3
}
```

## MCP integration (wired up)

The MCP server registers both UIs:

| Tool | Resource | Purpose |
|------|----------|---------|
| `quick_pass` | `quick-pass.html` | Quick discard by title/URL (before distill) |
| `distill` | `bookmark-review.html` | Post-distill review with summaries |

Vanilla HTML files load the MCP Apps SDK from unpkg. No build step. The UIs call `app.callServerTool("discard_bookmarks", ...)` and `promote_bookmarks` when the host supports it; otherwise they copy IDs to clipboard.
