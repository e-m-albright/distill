"""Bookmark list, discard, restore, and single-URL summary endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.status import BookmarkStatus, StatusFilter
from app.schemas.distill import BookmarkListResponse, BookmarkSchema, BriefItemSchema
from app.services.bookmark_service import (
    discard_bookmarks as svc_discard,
)
from app.services.bookmark_service import (
    get_bookmark_by_id,
)
from app.services.bookmark_service import (
    list_bookmarks as svc_list,
)
from app.services.bookmark_service import (
    move_bookmarks as svc_move,
)
from app.services.bookmark_service import (
    purge_bookmarks as svc_purge,
)
from app.services.bookmark_service import (
    restore_bookmarks as svc_restore,
)
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
    if include_discarded:
        sf = StatusFilter.ALL
    else:
        try:
            sf = StatusFilter(status)
        except ValueError:
            sf = StatusFilter.ACTIVE
    items, total = await svc_list(
        db, category=category, folder=folder, status_filter=sf, limit=limit, offset=offset
    )
    return BookmarkListResponse(
        items=[BookmarkSchema.model_validate(b) for b in items],
        total=total,
    )


class BulkIdsRequest(BaseModel):
    """Request body for bulk operations."""
    ids: list[int]


class MoveToRequest(BaseModel):
    """Request to move bookmarks to preview or view."""
    ids: list[int]
    status: str  # "preview" | "view"


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_bookmark(
    bookmark_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a bookmark as discarded (soft delete)."""
    b = await get_bookmark_by_id(db, bookmark_id)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    await svc_discard(db, [bookmark_id])


@router.post("/discard-bulk", status_code=status.HTTP_200_OK)
async def discard_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Bulk soft-delete (discard) bookmarks by ID. Reversible via restore-bulk."""
    discarded = await svc_discard(db, body.ids)
    return {"discarded": len(discarded)}


@router.post("/purge-bulk", status_code=status.HTTP_200_OK)
async def purge_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Permanently delete soft-deleted bookmarks. Only purges items in discard status. Irreversible."""
    count = await svc_purge(db, body.ids)
    return {"purged": count}


@router.post("/restore-bulk", status_code=status.HTTP_200_OK)
async def restore_bookmarks_bulk(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Restore soft-deleted bookmarks from discard back to unreviewed."""
    restored = await svc_restore(db, body.ids)
    return {"restored": len(restored)}


@router.post("/move-bulk", status_code=status.HTTP_200_OK)
async def move_bookmarks_bulk(
    body: MoveToRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Move bookmarks to preview (AI fetch) or view (user's collection)."""
    try:
        target = BookmarkStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be 'preview' or 'view'",
        )
    if target not in (BookmarkStatus.PREVIEW, BookmarkStatus.VIEW):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be 'preview' or 'view'",
        )
    moved = await svc_move(db, body.ids, target)
    return {"moved": len(moved)}


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
