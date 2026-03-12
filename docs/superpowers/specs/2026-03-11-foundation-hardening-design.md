# Foundation Hardening — Design Spec

**Date:** 2026-03-11
**Goal:** Improve code quality, architecture, and test coverage without changing user-visible behavior.

---

## 1. Status Enum & Model Cleanup

**Problem:** Status values (`unreviewed`, `preview`, `view`, `discard`, `active`, `discarded`, `kept`, `all`) are hardcoded strings scattered across `mcp_server.py`, `bookmark.py`, `bookmarks.py`, `ingest.py`, `distill.py`, and `cache_service.py`. Typos are invisible. Legacy aliases (`active` = `unreviewed`, `discarded` = `discard`) are handled ad-hoc.

**Design:**

Create `app/models/status.py`:

```python
from enum import StrEnum

class BookmarkStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"

class StatusFilter(StrEnum):
    """Virtual filters that map to one or more BookmarkStatus values."""
    ACTIVE = "active"       # alias for UNREVIEWED
    KEPT = "kept"           # all non-discard
    ALL = "all"             # no filter
    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"
    DISCARDED = "discarded" # legacy alias for DISCARD (backwards compat)
```

- `BookmarkStatus` is the set of real DB values (4 values). Used for writing/storing status.
- `StatusFilter` is the set of valid query parameters (8 values including aliases). Used only for reads/queries.
- A helper `resolve_status_filter(f: StatusFilter) -> list[BookmarkStatus] | None` maps filters to DB conditions (`None` = no filter for `ALL`). `DISCARDED` maps to `[BookmarkStatus.DISCARD]`.
- Replace every raw string comparison with enum usage.
- The existing `_migrate_status_values` startup migration already normalizes `active -> unreviewed`, `discarded -> discard`, `promoted -> view`. No new migration needed — just verify it continues to work after enum adoption.

**Files changed:** `app/models/status.py` (new), `app/models/bookmark.py`, `app/mcp_server.py`, `app/api/routes/bookmarks.py`, `app/api/routes/ingest.py`, `app/schemas/distill.py`, `app/services/cache_service.py`.

---

## 2. MCP Server Decomposition

**Problem:** `mcp_server.py` is 722 lines containing server setup, UI resource loading, CSP config, and 30+ tool definitions spanning ingest, organize, triage, preview, manage, and view workflows.

**Design:**

Restructure into:

```
app/
  mcp/
    __init__.py          # Empty
    server.py            # FastMCP app creation, resource loading, CSP, logging setup
    tools/
      __init__.py        # Empty
      ingest.py          # ingest_bookmarks
      organize.py        # organize_bookmarks, list_groups
      triage.py          # list_bookmarks, list_folders, triage, list_by_status,
                         #   get_status_summary, reconcile_status, verify_bookmark_status
      preview.py         # preview, summarize_bookmark
      manage.py          # move_to_preview, move_to_view, discard_bookmarks,
                         #   suggest_discard, restore_from_discard, purge_bookmarks
                         #   (discard_bookmark singular is removed — use discard_bookmarks with [id])
      view.py            # list_view
```

**Pattern:** Each tool module defines functions that take the `mcp` instance and register tools on it. `server.py` creates the `mcp` instance, loads resources, and calls each module's registration function.

```python
# app/mcp/tools/view.py
def register(mcp: FastMCP):
    @mcp.tool()
    async def list_view(limit: int = 100) -> str:
        ...
```

```python
# app/mcp/server.py
mcp = FastMCP("distillation", ...)
from app.mcp.tools import ingest, organize, triage, preview, manage, view
for module in [ingest, organize, triage, preview, manage, view]:
    module.register(mcp)
```

**UI resources** (`triage.html`, `preview.html`, `view.html`) stay in `mcp-app/`. Resource loading and CSP config live in `server.py`.

**Migration:** `app/mcp_server.py` becomes a thin re-export of `app.mcp.server:mcp` for backwards compatibility (existing `justfile` and install scripts reference it).

**Files changed:** `app/mcp/` (new package), `app/mcp_server.py` (reduced to re-export).

---

## 3. Unify REST API & MCP Logic

**Problem:** API routes and MCP tools duplicate DB queries and business logic. For example, listing bookmarks with filters, moving between statuses, and bulk discard all have parallel implementations.

**Design:**

Create `app/services/bookmark_service.py` with shared operations:

```python
async def list_bookmarks(session, *, category, folder, status_filter, limit, offset) -> tuple[list[Bookmark], int]
async def move_bookmarks(session, ids: list[int], target_status: BookmarkStatus) -> list[Bookmark]
    # target_status constrained to PREVIEW and VIEW only; use discard/restore for those transitions
async def discard_bookmarks(session, ids: list[int]) -> list[Bookmark]
async def restore_bookmarks(session, ids: list[int]) -> list[Bookmark]
    # validates bookmark is in DISCARD status before restoring
async def purge_bookmarks(session, ids: list[int]) -> int  # returns count deleted
async def get_status_summary(session) -> dict[str, int]
async def get_bookmark_by_id(session, id: int) -> Bookmark | None
async def ingest_bookmarks(session, entries: list[BookmarkEntry]) -> tuple[int, int]  # (new, total)
```

Both API routes and MCP tools call these functions. Each service function takes a `session` parameter — the caller is responsible for session lifecycle.

The existing `distill_service.py`, `organize_service.py`, `cache_service.py`, and `content_fetcher.py` stay as-is (they're already well-scoped).

The REST `/preview` and `/distill` endpoints in `ingest.py` are out of scope for service extraction — they orchestrate fetch + distill which is already handled by `distill_service.py`. Only the CRUD operations on bookmarks are unified.

**Files changed:** `app/services/bookmark_service.py` (new), `app/api/routes/bookmarks.py` (simplified), `app/api/routes/ingest.py` (simplified), `app/mcp/tools/*.py` (use service layer).

---

## 4. Error Handling Improvements

**Problem:** `distill_service.distill_content()` processes a batch — if any item fails, behavior is unclear. Content fetcher returns `ExtractedContent(success=False)` but callers handle this inconsistently. Inline migrations lack clear idempotency guarantees.

**Design:**

**Distill service:** Process items individually within the batch. Failed items get a `BriefItem` with `summary="Failed to process"`, `key_points=[]`, `view=False`. The batch always returns results for every input item. Log errors per item.

**Content fetcher:** Already returns `success=False` on failure — no change needed. Callers (distill service, MCP preview tool) must check `success` before sending to LLM.

**Inline migrations:** Add a comment block at the top of each migration function documenting what it does and confirming idempotency. Rename for clarity:
- `_migrate_add_bookmark_status` → `_ensure_status_column`
- `_migrate_add_group_and_cache` → `_ensure_category_and_cache_columns`
- `_migrate_status_values` → `_normalize_legacy_status_values`

**Files changed:** `app/services/distill_service.py`, `app/db/session.py`.

---

## 5. Critical-Path Tests (~15-20 tests)

**Problem:** 3 existing tests (health, HTML parser, JSON parser). No coverage of status logic, cache, bookmark operations, or API routes beyond health.

**Design:**

```
tests/
  conftest.py                  # Shared fixtures (db_session, client) — exists
  test_api.py                  # Health test — exists, expand with route tests
  test_bookmark_parser.py      # Parser tests — exists, add edge cases
  test_status.py               # NEW: enum resolution, filter mapping
  test_bookmark_service.py     # NEW: list, move, discard, restore, purge, ingest
  test_cache_service.py        # NEW: cache hit, miss, expiry, update
  test_api_bookmarks.py        # NEW: API route integration tests
```

**Test breakdown:**

| Area | Tests | Notes |
|------|-------|-------|
| Status enum | 3 | resolve_status_filter for active/kept/all |
| Bookmark service | 6 | list w/ filters, move, discard, restore, purge, ingest dedup |
| Cache service | 3 | fresh hit, expired miss, update |
| Bookmark parser | 3 | empty file, malformed HTML, duplicate URLs |
| API routes | 4 | ingest, list, discard-bulk, restore-bulk |

**Total: ~19 tests.** All use in-memory SQLite. No LLM mocking — tests that would need Gemini test the service interface, not the LLM call.

**Files changed:** `tests/test_status.py`, `tests/test_bookmark_service.py`, `tests/test_cache_service.py`, `tests/test_api_bookmarks.py` (all new), `tests/test_bookmark_parser.py` (expanded).

---

## Ordering & Dependencies

```
1. Status Enum          (no dependencies)
2. MCP Decomposition    (depends on 1 — pure structural refactor, moves existing code into modules)
3. Bookmark Service     (depends on 1 — extract shared logic, update API routes + MCP tool modules)
4. Error Handling       (depends on 1 — uses enum in distill)
5. Tests                (depends on 1, 2, 3, 4 — tests the final interfaces)
```

Step 2 (MCP decomposition) is a pure code-move refactor — no logic changes. Step 3 then extracts shared logic into the service layer, updating both the API routes and the now-decomposed MCP tool modules. This avoids the circular dependency of modifying `app/mcp/tools/*.py` before those files exist.

Each sub-project is a separate commit. The app should work identically after each step.

---

## Out of Scope

- New features (write_artifact, progress tracking, streaming, etc.)
- Auth layer
- Alembic or migration tooling changes
- MCP UI changes (triage.html, preview.html, view.html)
- Changes to external service integrations (Jina, Gemini, YouTube)
