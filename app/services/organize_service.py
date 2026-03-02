"""AI-assisted bookmark organization into user-defined groups."""

from typing import Any

import instructor
import structlog
from pydantic import BaseModel

from app.config import settings


log = structlog.get_logger()


class BookmarkAssignment(BaseModel):
    """Single bookmark assigned to a category."""

    index: int  # 0-based index into the input list
    category: str


class OrganizeResult(BaseModel):
    """Result of organizing bookmarks into categories."""

    assignments: list[BookmarkAssignment]


def _get_client() -> Any:
    """Get Gemini client via Instructor."""
    kwargs: dict[str, Any] = {"async_client": True, "mode": instructor.Mode.JSON}
    if settings.google_api_key:
        kwargs["api_key"] = settings.google_api_key
    return instructor.from_provider("google/gemini-2.5-flash", **kwargs)


async def organize_bookmarks(
    items: list[tuple[int, str, str, str]],  # (id, title, url, folder)
    categories: list[str],
) -> list[tuple[int, str]]:
    """Assign each bookmark to one of the given categories based on title/url/folder.
    Returns list of (bookmark_id, category)."""
    if not items or not categories:
        return []

    client = _get_client()
    lines: list[str] = []
    for i, (_bid, title, url, folder) in enumerate(items):
        lines.append(f"{i}: {title} | {url} | folder: {folder}")

    prompt = f"""Assign each bookmark below to exactly one of these categories: {", ".join(str(c) for c in categories)}.
Use title, URL, and folder to infer the best fit. If unclear, pick the most likely category.
Categories: {categories}

Bookmarks (index: title | url | folder):
{chr(10).join(lines)}

Return one assignment per bookmark. Index is 0-based."""

    try:
        result: OrganizeResult = await client.create(  # type: ignore[misc]
            messages=[{"role": "user", "content": prompt}],
            response_model=OrganizeResult,
        )
        out: list[tuple[int, str]] = []
        cat_set = set(categories)
        for a in result.assignments:
            if 0 <= a.index < len(items):
                bid = items[a.index][0]
                cat = a.category if a.category in cat_set else categories[0]
                out.append((bid, cat))
        return out
    except Exception as e:
        log.exception("organize_failed", error=str(e))
        raise
