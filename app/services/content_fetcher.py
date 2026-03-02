"""Fetch and extract main content from URLs."""

import httpx
import structlog
import trafilatura
from pydantic import BaseModel

from app.config import settings


log = structlog.get_logger()


class ExtractedContent(BaseModel):
    """Extracted main content from a URL."""

    url: str
    title: str
    text: str
    success: bool
    error: str | None = None


async def fetch_and_extract(url: str) -> ExtractedContent:
    """Fetch URL and extract main content using trafilatura."""
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

        result = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        metadata = trafilatura.extract_metadata(html)

        if result:
            title = (metadata.title if metadata else None) or url
            return ExtractedContent(
                url=url,
                title=title,
                text=result.strip(),
                success=True,
            )

        # Fallback: return first chunk of text
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 5000:
            text = text[:5000] + "..."
        title = (metadata.title if metadata else None) or url
        return ExtractedContent(
            url=url,
            title=title,
            text=text or "(No content extracted)",
            success=bool(text),
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
        log.exception("extract_failed", url=url)
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
        )
