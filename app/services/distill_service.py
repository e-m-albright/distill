"""LLM-based preview: per-link summarization. Jina/Gemini for fetch; Gemini for YouTube."""

from typing import Any

import instructor
import structlog
from pydantic import BaseModel, Field

from app.config import settings
from app.services.content_fetcher import ExtractedContent


log = structlog.get_logger()


class BriefItem(BaseModel):
    """A single item in the preview (per-link only)."""

    title: str
    url: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    view: bool = True  # True = worth viewing; False = skip/discard


class DistilledBrief(BaseModel):
    """Structured preview output (per-link, no overview)."""

    items: list[BriefItem]


def _get_client() -> Any:
    """Get Gemini client via Instructor."""
    kwargs: dict[str, Any] = {"async_client": True, "mode": instructor.Mode.GENAI_STRUCTURED_OUTPUTS}
    if settings.google_api_key:
        kwargs["api_key"] = settings.google_api_key
    return instructor.from_provider("google/gemini-2.5-flash", **kwargs)


async def _summarize_youtube(url: str) -> BriefItem:
    """Summarize YouTube video via Gemini native video API."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.google_api_key or "")
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_uri(file_uri=url, mime_type="video/mp4"),
                "Summarize this video in 1-2 sentences. Extract 0-3 key points. "
                "Is it worth the user's time to watch? Reply with JSON: "
                '{"title":"...","summary":"...","key_points":["..."],"view":true|false}',
            ],
        )
        text = (response.text or "").strip()
        # Parse JSON from response (may be wrapped in markdown)
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        import json

        data = json.loads(text)
        return BriefItem(
            title=data.get("title", url),
            url=url,
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            view=data.get("view", True),
        )
    except Exception as e:
        log.warning("youtube_summarize_failed", url=url, error=str(e))
        return BriefItem(
            title=url,
            url=url,
            summary=f"Could not summarize video: {e}",
            key_points=[],
            view=False,
        )


async def distill_content(contents: list[ExtractedContent]) -> DistilledBrief:
    """Preview a list of fetched contents. Per-link only, no overview."""
    if not contents:
        return DistilledBrief(items=[])

    # Handle YouTube URLs separately (Gemini native video API)
    youtube_items: list[tuple[int, BriefItem]] = []
    text_contents: list[tuple[int, ExtractedContent]] = []
    for i, c in enumerate(contents):
        if getattr(c, "source", "") == "youtube":
            item = await _summarize_youtube(c.url)
            youtube_items.append((i, item))
        else:
            text_contents.append((i, c))

    # Process text items via Instructor
    if not text_contents:
        # All YouTube
        ordered = sorted(youtube_items, key=lambda x: x[0])
        return DistilledBrief(items=[item for _, item in ordered])

    client = _get_client()
    context_parts: list[str] = []
    indices: list[int] = []
    for i, c in text_contents:
        if c.success and c.text:
            text_preview = c.text[:8000] + "..." if len(c.text) > 8000 else c.text
            context_parts.append(f"--- Item {i + 1}: {c.title} ({c.url}) ---\n{text_preview}")
        else:
            context_parts.append(
                f"--- Item {i + 1}: {c.title} ({c.url}) ---\n[Failed to fetch or empty]"
            )
        indices.append(i)

    context = "\n\n".join(context_parts)
    prompt = f"""You are a preview assistant. Given the following content items, produce a structured preview for EACH item.

For each item:
1. Write a 1-2 sentence summary.
2. Extract 0-3 key points if valuable.
3. Set view=True if the content is worth the user's time (informative, actionable, or personally relevant). Set view=False for low-value content (ads, fluff, redundant, noise, or failed fetch).

No overall overview. Per-item only.

Content:

{context}
"""

    try:
        brief: DistilledBrief = await client.create(  # type: ignore[misc]
            messages=[{"role": "user", "content": prompt}],
            response_model=DistilledBrief,
        )
        idx_to_item = {indices[j]: brief.items[j] for j in range(len(brief.items))}
    except Exception as e:
        log.exception("distill_failed", error=str(e))
        # Create failure items for all text contents instead of crashing
        idx_to_item = {}
        for i, c in text_contents:
            idx_to_item[i] = BriefItem(
                title=c.title or c.url,
                url=c.url,
                summary="Failed to process",
                key_points=[],
                view=False,
            )

    for i, item in youtube_items:
        idx_to_item[i] = item
    ordered_items = [idx_to_item[i] for i in sorted(idx_to_item)]
    return DistilledBrief(items=ordered_items)


async def summarize_single(
    url: str,
    *,
    cached_summary: str | None = None,
    cached_key_points: list[str] | None = None,
) -> BriefItem:
    """Fetch and summarize a single URL. Uses cache when provided."""
    if cached_summary:
        return BriefItem(
            title=url,
            url=url,
            summary=cached_summary,
            key_points=cached_key_points or [],
            view=True,
        )
    from app.services.content_fetcher import fetch_and_extract

    content = await fetch_and_extract(url)
    if getattr(content, "source", "") == "youtube":
        return await _summarize_youtube(url)
    brief = await distill_content([content])
    if brief.items:
        return brief.items[0]
    return BriefItem(
        title=content.title,
        url=url,
        summary="[Failed to fetch or extract content]" if not content.success else "(No content)",
        key_points=[],
        view=False,
    )
