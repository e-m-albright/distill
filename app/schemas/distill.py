"""Schemas for distill API."""

from pydantic import BaseModel, ConfigDict, Field


class BriefItemSchema(BaseModel):
    """A single item in the distilled brief."""

    title: str
    url: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    keep: bool = True


class DistilledBriefSchema(BaseModel):
    """Structured brief output."""

    overview: str
    items: list[BriefItemSchema]
    discarded_count: int = 0


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
