"""Bookmark list, discard, and single-URL summary endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.bookmark import Bookmark
from app.schemas.distill import BookmarkListResponse, BookmarkSchema, BriefItemSchema
from app.services.cache_service import get_cached_summary, update_cache
from app.services.distill_service import summarize_single


router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    folder: str | None = None,
    category: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    include_discarded: bool = False,
    db: AsyncSession = Depends(get_db),
) -> BookmarkListResponse:
    """List stored bookmarks. Filter by folder, category, status."""
    status_filter = [] if include_discarded or status == "all" else [Bookmark.status == status]
    folder_filter = [Bookmark.folder == folder] if folder else []
    category_filter = [Bookmark.category == category] if category else []

    count_result = await db.execute(
        select(func.count())
        .select_from(Bookmark)
        .where(*status_filter, *folder_filter, *category_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Bookmark)
        .where(*status_filter, *folder_filter, *category_filter)
        .order_by(Bookmark.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()
    return BookmarkListResponse(
        items=[BookmarkSchema.model_validate(b) for b in items],
        total=total,
    )


class BulkIdsRequest(BaseModel):
    """Request body for bulk operations."""

    ids: list[int]


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_bookmark(
    bookmark_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a bookmark as discarded (soft delete)."""
    result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
    bookmark = result.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    bookmark.status = "discarded"
    await db.commit()


@router.post("/discard-bulk", status_code=status.HTTP_200_OK)
async def discard_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Bulk discard bookmarks by ID."""
    discarded = 0
    for bid in body.ids:
        result = await db.execute(select(Bookmark).where(Bookmark.id == bid))
        b = result.scalar_one_or_none()
        if b:
            b.status = "discarded"
            discarded += 1
    await db.commit()
    return {"discarded": discarded}


@router.post("/promote-bulk", status_code=status.HTTP_200_OK)
async def promote_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Mark bookmarks for deeper review (promoted)."""
    promoted = 0
    for bid in body.ids:
        result = await db.execute(select(Bookmark).where(Bookmark.id == bid))
        b = result.scalar_one_or_none()
        if b:
            b.status = "promoted"
            promoted += 1
    await db.commit()
    return {"promoted": promoted}


class SummarizeRequest(BaseModel):
    """Request to summarize a single URL."""

    url: str


@router.post("/summarize", response_model=BriefItemSchema)
async def summarize_bookmark(
    body: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
) -> BriefItemSchema:
    """Fetch and summarize a single URL. Uses cache when available."""
    url = body.url
    if not url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http or https",
        )
    cached = await get_cached_summary(db, url)
    if cached:
        summary, key_points = cached
        item = await summarize_single(url, cached_summary=summary, cached_key_points=key_points)
    else:
        item = await summarize_single(url)
        await update_cache(db, url, item.summary, item.key_points)
    await db.commit()
    return BriefItemSchema.model_validate(item)
