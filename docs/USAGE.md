# Distillation Usage Guide

## How the MCP Server Gets Your Bookmarks

**You give Claude the file path.** When you say "ingest my bookmarks from ~/Downloads/bookmarks.html", Claude calls the `ingest_bookmarks` tool with that path. The MCP server reads the file from your filesystem and parses it. No upload—Claude passes the path you provide.

**Export first:** In Chrome, go to Bookmarks → ⋮ → Export bookmarks. Save as HTML (or use Chrome JSON from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`).

---

## Workflow: Ingest → Organize → Triage → Preview → View

**Status values (strict):**
| Status | Meaning |
|--------|---------|
| `active` | Unreviewed only (organized, not yet moved to preview/view) |
| `kept` | All non-discard (unreviewed + preview + view) |
| `unreviewed` | Not yet triaged |
| `preview` | AI fetch/summarize |
| `view` | Your collection to visit |
| `discard` | Soft-deleted (tossed). Reversible. |
| `all` | No status filter |

**Filtering:** `list_bookmarks` and `triage` use exact match for category and folder. When you move bookmarks to `view` or `preview`, they no longer appear in `status="active"`. Use `status="kept"` to see all non-discard. Use `get_status_summary()` and `reconcile_status(id)` to verify moves.

### 1. Ingest

```
"Ingest my bookmarks from ~/Downloads/bookmarks.html"
```

### 2. Organize (Assign Groups, Incremental)

Run `list_groups` first to see counts. Then run `organize_bookmarks` repeatedly until Unorganized is 0:

```
"List my groups"
"Organize my bookmarks into: low_value, high_value, AI, cooking, parenting, work, news"
→ Run again until "Unorganized remaining: 0"
```

### 3. Triage (Review by Title/URL)

Use `triage` for an interactive UI, or `list_bookmarks` for text. **Claude will not auto-discard**—it presents candidates for you to confirm.

```
"Triage for category cooking, limit 50"
→ Interactive UI shows title/URL; select and discard
```

Or: `"List bookmarks in category 'cooking'"` then confirm which to discard.

### 4. Preview (AI Summarize Per Link)

After triage, run preview to fetch and summarize. **Per-link only** (no overview). Confirm with Claude which links to preview vs put aside for view.

```
"Preview the cooking bookmarks, limit 30"
```

Each item gets: summary, key points, view/discard suggestion. **Summaries are cached** (30-day TTL).

### 5. Move to View or Discard

From preview results:

```
"Move bookmarks 7, 12, 19 to view"
"Discard bookmarks 15, 23, 31"
```

View = your collection to visit directly. Discard = soft-deleted (reversible).

### 6. Restore from Discard

If you discarded by mistake:

```
"Restore bookmarks 15, 23, 31 from discard"
→ restore_from_discard([15, 23, 31])
```

### 7. Purge (Permanent Delete)

When ready to permanently remove discarded bookmarks:

```
"Purge the discarded bookmarks 15, 23, 31"
→ purge_bookmarks([15, 23, 31])
```

Only items in discard status can be purged. Irreversible.

### 8. View Your Collection

```
"Show my view links"
→ list_view opens the View UI
```

---

## Caching

- **Preview** — Summaries stored per bookmark. Re-preview uses cache (30-day TTL).
- **summarize_bookmark** — Single-URL summaries cached.
- **Organize** — No fetch; uses title/URL/folder only (cheap).

---

## Tools Reference

| Tool | Purpose |
|------|---------|
| `ingest_bookmarks` | Ingest from file path |
| `organize_bookmarks` | Assign categories (AI-driven) |
| `list_groups` | See counts by status |
| `list_folders` | See browser folder structure |
| `list_bookmarks` | List by title/URL (text) |
| `list_by_status` | Debug: list all bookmarks by status across categories |
| `reconcile_status` | Debug: verify a bookmark's actual status in the backend |
| `verify_bookmark_status` | Debug: same as reconcile_status |
| `get_status_summary` | Debug: reconciliation report (total, active, preview, view, discard) |
| `triage` | Triage UI: review by title/URL |
| `preview` | Batch summarize (per-link) + preview UI |
| `list_view` | View UI: links in your collection |
| `summarize_bookmark` | Single URL (uses cache) |
| `discard_bookmarks` | Bulk soft-delete (discard). Reversible. |
| `restore_from_discard` | Restore soft-deleted bookmarks to unreviewed |
| `purge_bookmarks` | Permanently delete discarded bookmarks. Irreversible. |
| `suggest_discard` | Present IDs for user to confirm before discarding |
| `move_to_preview` | Move to preview (AI fetch) |
| `move_to_view` | Move to view (your collection) |
| `discard_bookmark` | Single discard |

**Category vs folder:** Category = assigned by the AI (organize). Folder = from browser export. Both use exact match. `list_bookmarks(category="design_ux")` returns bookmarks in that category. `list_bookmarks(status="discard")` returns soft-deleted bookmarks.
