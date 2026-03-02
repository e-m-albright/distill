"""LLM-based distillation: filter and summarize content into a brief."""

from pydantic import BaseModel, Field

import instructor
import openai
import structlog

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


def _get_client():
    """Get OpenAI client with Instructor patch."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key or "")
    return instructor.from_openai(client, mode=instructor.Mode.JSON)


async def distill_content(contents: list[ExtractedContent]) -> DistilledBrief:
    """Distill a list of extracted contents into a structured brief."""
    if not contents:
        return DistilledBrief(overview="No content to distill.", items=[], discarded_count=0)

    client = _get_client()

    # Build context for the LLM
    context_parts: list[str] = []
    for i, c in enumerate(contents):
        if c.success and c.text:
            text_preview = c.text[:3000] + "..." if len(c.text) > 3000 else c.text
            context_parts.append(f"--- Item {i + 1}: {c.title} ({c.url}) ---\n{text_preview}")
        else:
            context_parts.append(f"--- Item {i + 1}: {c.title} ({c.url}) ---\n[Failed to fetch or empty]")

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
        brief = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=DistilledBrief,
            messages=[{"role": "user", "content": prompt}],
        )
        brief.discarded_count = sum(1 for i in brief.items if not i.keep)
        return brief
    except Exception as e:
        log.exception("distill_failed", error=str(e))
        raise
