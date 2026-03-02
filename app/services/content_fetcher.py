"""Fetch content from URLs. AI handles extraction and summarization."""

import httpx
import structlog
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.config import settings


log = structlog.get_logger()


class ExtractedContent(BaseModel):
    """Fetched content from a URL (minimal processing; AI does extraction)."""

    url: str
    title: str
    text: str
    success: bool
    error: str | None = None


async def fetch_and_extract(url: str) -> ExtractedContent:
    """Fetch URL and return content. Strips scripts/styles only; AI extracts meaning."""
    try:
        async with httpx.AsyncClient(
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "Distillation/1.0 (Content extraction for personal use)",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        if len(html) > settings.max_content_length:
            html = html[: settings.max_content_length] + "..."

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 50_000:
            text = text[:50_000] + "..."
        title = (soup.title.string if soup.title else None) or url

        return ExtractedContent(
            url=url,
            title=title.strip() if title else url,
            text=text or "(No content)",
            success=bool(text.strip()),
        )

    except httpx.HTTPError as e:
        log.warning("fetch_failed", url=url, error=str(e))
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
        )
    except Exception as e:
        log.exception("fetch_failed", url=url)
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
        )
