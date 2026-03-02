"""Bookmark ingest and distill endpoints."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.bookmark import Bookmark
from app.schemas.distill import (
    BriefItemSchema,
    DistilledBriefSchema,
    IngestBookmarksResponse,
)
from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html
from app.services.content_fetcher import ExtractedContent, fetch_and_extract
from app.services.distill_service import distill_content


router = APIRouter(prefix="", tags=["ingest", "distill"])


@router.post("/ingest/bookmarks", response_model=IngestBookmarksResponse)
async def ingest_bookmarks(
    file: UploadFile,
    format: Literal["html", "json"] = "html",
    db: AsyncSession = Depends(get_db),
) -> IngestBookmarksResponse:
    """Accept HTML or JSON bookmark export, parse, and store."""
    content = (await file.read()).decode("utf-8", errors="replace")
    if format == "json":
        entries = list(parse_chrome_json(content))
    else:
        entries = list(parse_netscape_html(content))

    ingested = 0
    for entry in entries:
        if not entry.url or not entry.url.startswith("http"):
            continue
        # Upsert by URL
        result = await db.execute(select(Bookmark).where(Bookmark.url == entry.url))
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(
                Bookmark(
                    url=entry.url,
                    title=entry.title,
                    folder=entry.folder,
                    added=entry.added,
                ),
            )
            ingested += 1

    await db.commit()
    return IngestBookmarksResponse(ingested=ingested, total=len(entries))


@router.post("/distill", response_model=DistilledBriefSchema)
async def distill(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DistilledBriefSchema:
    """Fetch content from stored bookmarks, distill into a brief."""
    from sqlalchemy import select

    result = await db.execute(select(Bookmark).where(Bookmark.status == "active").limit(limit))
    bookmarks = result.scalars().all()
    if not bookmarks:
        return DistilledBriefSchema(
            overview="No bookmarks to distill. Ingest some first via POST /ingest/bookmarks.",
            items=[],
            discarded_count=0,
        )

    # Fetch content in parallel (bounded concurrency)
    sem = asyncio.Semaphore(5)

    async def fetch_one(b: Bookmark) -> ExtractedContent:
        async with sem:
            return await fetch_and_extract(b.url)

    contents = await asyncio.gather(*[fetch_one(b) for b in bookmarks])
    brief = await distill_content(list(contents))

    return DistilledBriefSchema(
        overview=brief.overview,
        items=[BriefItemSchema.model_validate(i) for i in brief.items],
        discarded_count=brief.discarded_count,
    )
