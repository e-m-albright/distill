"""Bookmark status enum and filter resolution."""

from enum import StrEnum


class BookmarkStatus(StrEnum):
    """Real DB status values. Used for writing/storing."""

    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"


class StatusFilter(StrEnum):
    """Valid query parameter values. Used only for reads/queries."""

    ACTIVE = "active"
    KEPT = "kept"
    ALL = "all"
    UNREVIEWED = "unreviewed"
    PREVIEW = "preview"
    VIEW = "view"
    DISCARD = "discard"
    DISCARDED = "discarded"


def resolve_status_filter(f: StatusFilter) -> list[BookmarkStatus] | None:
    """Map a StatusFilter to DB conditions. Returns None for ALL (no filter)."""
    if f == StatusFilter.ALL:
        return None
    if f == StatusFilter.ACTIVE:
        return [BookmarkStatus.UNREVIEWED]
    if f == StatusFilter.KEPT:
        return [BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW]
    if f in (StatusFilter.DISCARD, StatusFilter.DISCARDED):
        return [BookmarkStatus.DISCARD]
    # Direct match: UNREVIEWED, PREVIEW, VIEW
    return [BookmarkStatus(f.value)]
