"""Bookmark ingest and distill endpoints."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, UploadFile
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


router = APIRouter(prefix="", tags=["ingest", "preview"])


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

    from app.services.bookmark_service import ingest_bookmarks as svc_ingest
    new_count, total = await svc_ingest(db, entries)
    return IngestBookmarksResponse(ingested=new_count, total=total)


@router.post("/distill", response_model=DistilledBriefSchema)
@router.post("/preview", response_model=DistilledBriefSchema)
async def preview(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DistilledBriefSchema:
    """Fetch content from stored bookmarks, preview (summarize) per link."""
    from sqlalchemy import select

    result = await db.execute(
        select(Bookmark)
        .where(
            Bookmark.status.in_(["unreviewed", "preview"]),
        )
        .limit(limit)
    )
    bookmarks = result.scalars().all()
    if not bookmarks:
        return DistilledBriefSchema(items=[])

    sem = asyncio.Semaphore(10)

    async def fetch_one(b: Bookmark) -> ExtractedContent:
        async with sem:
            return await fetch_and_extract(b.url)

    contents = await asyncio.gather(*[fetch_one(b) for b in bookmarks])
    brief = await distill_content(list(contents))

    return DistilledBriefSchema(items=[BriefItemSchema.model_validate(i) for i in brief.items])
