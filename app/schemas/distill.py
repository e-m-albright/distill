"""Schemas for distill API."""

from pydantic import BaseModel, ConfigDict, Field


class BriefItemSchema(BaseModel):
    """A single item in the preview."""

    title: str
    url: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    view: bool = True


class DistilledBriefSchema(BaseModel):
    """Structured preview output (per-link only)."""

    items: list[BriefItemSchema]


class IngestBookmarksResponse(BaseModel):
    """Response from bookmark ingest."""

    ingested: int
    total: int


class BookmarkSchema(BaseModel):
    """Bookmark in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    folder: str
    status: str
    category: str = ""


class BookmarkListResponse(BaseModel):
    """Paginated bookmark list."""

    items: list[BookmarkSchema]
    total: int
