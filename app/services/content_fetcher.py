"""Fetch content from URLs. Jina Reader for rich extraction; httpx fallback; Gemini for YouTube."""

import re

import httpx
import structlog
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.config import settings


log = structlog.get_logger()

# YouTube patterns (watch, shorts, youtu.be)
_YOUTUBE_RE = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/)[\w-]+",
    re.IGNORECASE,
)


def _is_youtube(url: str) -> bool:
    return bool(_YOUTUBE_RE.match(url.strip()))


class ExtractedContent(BaseModel):
    """Fetched content from a URL (minimal processing; AI extracts meaning)."""

    url: str
    title: str
    text: str
    success: bool
    error: str | None = None
    source: str = "html"  # html | jina | youtube (youtube = pass URL to Gemini)


async def _fetch_jina(url: str) -> ExtractedContent:
    """Fetch via Jina Reader (handles Reddit, paywalls, JS-heavy sites)."""
    jina_url = f"https://r.jina.ai/{url}"
    headers: dict[str, str] = {"X-Return-Format": "markdown"}
    if settings.jina_api_key:
        headers["Authorization"] = f"Bearer {settings.jina_api_key}"
    try:
        async with httpx.AsyncClient(
            timeout=min(settings.fetch_timeout_seconds, 60),
            follow_redirects=True,
        ) as client:
            response = await client.get(jina_url, headers=headers)
            response.raise_for_status()
            text = response.text.strip()
        if len(text) > 50_000:
            text = text[:50_000] + "..."
        title = url
        if "# " in text[:200]:
            first_line = text.split("\n")[0]
            if first_line.startswith("# "):
                title = first_line[2:].strip()
        return ExtractedContent(
            url=url,
            title=title or url,
            text=text or "",
            success=bool(text.strip()),
            source="jina",
        )
    except httpx.HTTPError as e:
        log.warning("jina_fetch_failed", url=url, error=str(e))
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
            source="jina",
        )


async def _fetch_httpx(url: str) -> ExtractedContent:
    """Fetch via httpx + BeautifulSoup (original fallback)."""
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
            source="html",
        )

    except httpx.HTTPError as e:
        log.warning("fetch_failed", url=url, error=str(e))
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
            source="html",
        )
    except Exception as e:
        log.exception("fetch_failed", url=url)
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=False,
            error=str(e),
            source="html",
        )


async def fetch_and_extract(url: str) -> ExtractedContent:
    """Fetch URL and return content. Jina for most; httpx fallback; YouTube passed to Gemini."""
    if _is_youtube(url):
        return ExtractedContent(
            url=url,
            title=url,
            text="",
            success=True,
            source="youtube",
        )

    # Try Jina first (handles Reddit, paywalls, JS-heavy sites)
    result = await _fetch_jina(url)
    if result.success and len(result.text.strip()) > 100:
        return result

    # Fallback to httpx for simple pages or when Jina fails
    if not result.success:
        return await _fetch_httpx(url)
    return result
