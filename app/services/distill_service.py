"""LLM-based distillation: filter and summarize content into a brief."""

from typing import Any

import instructor
import structlog
from pydantic import BaseModel, Field

from app.config import settings
from app.services.content_fetcher import ExtractedContent


log = structlog.get_logger()


class BriefItem(BaseModel):
    """A single item in the distilled brief."""

    title: str
    url: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    keep: bool = True


class DistilledBrief(BaseModel):
    """Structured brief output from distillation."""

    overview: str
    items: list[BriefItem]
    discarded_count: int = 0


def _get_client() -> Any:
    """Get Gemini client via Instructor. Uses GOOGLE_API_KEY env if not in settings."""
    kwargs: dict[str, Any] = {"async_client": True, "mode": instructor.Mode.JSON}
    if settings.google_api_key:
        kwargs["api_key"] = settings.google_api_key
    return instructor.from_provider("google/gemini-2.5-flash", **kwargs)


async def distill_content(contents: list[ExtractedContent]) -> DistilledBrief:
    """Distill a list of fetched contents into a structured brief."""
    if not contents:
        return DistilledBrief(overview="No content to distill.", items=[], discarded_count=0)

    client = _get_client()

    # Build context for the LLM (AI extracts and summarizes; we pass raw content)
    context_parts: list[str] = []
    for i, c in enumerate(contents):
        if c.success and c.text:
            # Gemini has large context; send more content for better extraction
            text_preview = c.text[:8000] + "..." if len(c.text) > 8000 else c.text
            context_parts.append(f"--- Item {i + 1}: {c.title} ({c.url}) ---\n{text_preview}")
        else:
            context_parts.append(
                f"--- Item {i + 1}: {c.title} ({c.url}) ---\n[Failed to fetch or empty]"
            )

    context = "\n\n".join(context_parts)

    prompt = f"""You are a distillation assistant. Given the following content items (bookmarks, articles, etc.), produce a structured brief.

For each item:
1. Write a 1-2 sentence summary.
2. Extract 0-3 key points if valuable.
3. Set keep=True if the content is worth retaining (informative, actionable, or personally relevant). Set keep=False for low-value content (ads, fluff, redundant, or noise).

Provide an overall overview (2-3 sentences) synthesizing the main themes across all content.

Content to distill:

{context}
"""

    try:
        brief: DistilledBrief = await client.create(  # type: ignore[misc]
            messages=[{"role": "user", "content": prompt}],
            response_model=DistilledBrief,
        )
        brief.discarded_count = sum(1 for item in brief.items if not item.keep)
        return brief
    except Exception as e:
        log.exception("distill_failed", error=str(e))
        raise


async def summarize_single(
    url: str,
    *,
    cached_summary: str | None = None,
    cached_key_points: list[str] | None = None,
) -> BriefItem:
    """Fetch and summarize a single URL. Uses cache when provided to avoid re-fetch/re-summarize."""
    if cached_summary:
        return BriefItem(
            title=url,
            url=url,
            summary=cached_summary,
            key_points=cached_key_points or [],
            keep=True,
        )
    from app.services.content_fetcher import fetch_and_extract

    content = await fetch_and_extract(url)
    brief = await distill_content([content])
    if brief.items:
        item = brief.items[0]
        return item
    return BriefItem(
        title=content.title,
        url=url,
        summary="[Failed to fetch or extract content]" if not content.success else "(No content)",
        key_points=[],
        keep=False,
    )
