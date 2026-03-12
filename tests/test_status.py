"""Tests for status enum and filter resolution."""

from app.models.status import BookmarkStatus, StatusFilter, resolve_status_filter


def test_resolve_active_returns_unreviewed() -> None:
    result = resolve_status_filter(StatusFilter.ACTIVE)
    assert result == [BookmarkStatus.UNREVIEWED]


def test_resolve_kept_returns_non_discard() -> None:
    result = resolve_status_filter(StatusFilter.KEPT)
    assert set(result) == {BookmarkStatus.UNREVIEWED, BookmarkStatus.PREVIEW, BookmarkStatus.VIEW}


def test_resolve_all_returns_none() -> None:
    result = resolve_status_filter(StatusFilter.ALL)
    assert result is None


def test_resolve_discarded_alias() -> None:
    result = resolve_status_filter(StatusFilter.DISCARDED)
    assert result == [BookmarkStatus.DISCARD]


def test_resolve_direct_status() -> None:
    assert resolve_status_filter(StatusFilter.PREVIEW) == [BookmarkStatus.PREVIEW]
    assert resolve_status_filter(StatusFilter.VIEW) == [BookmarkStatus.VIEW]
    assert resolve_status_filter(StatusFilter.DISCARD) == [BookmarkStatus.DISCARD]
    assert resolve_status_filter(StatusFilter.UNREVIEWED) == [BookmarkStatus.UNREVIEWED]
