# MCP App: Bookmark Review UI

Improved bookmark review UI for bulk triage (discard / promote). Designed to receive data from the `distill` tool and call `discard_bookmarks` / `promote_bookmarks` via MCP.

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

## MCP integration path

1. Add `distill_review` tool that returns this shape (with bookmark ids).
2. Register resource serving bundled HTML (React + `vite-plugin-singlefile`).
3. Link tool via `_meta.ui.resourceUri`.
4. In `ontoolresult`, pass brief to UI.
5. UI calls `app.callServerTool("discard_bookmarks", { bookmark_ids })` and `promote_bookmarks` — no clipboard paste.

## Running locally (preview)

```bash
cd mcp-app
npm install
npm run dev
```

Requires Vite + React setup (see MCP Apps SDK examples for full scaffold).
