"""Bookmark model."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bookmark(Base):
    """Stored bookmark from import."""

    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), index=True)
    title: Mapped[str] = mapped_column(String(512))
    folder: Mapped[str] = mapped_column(String(512), default="")
    added: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="active"
    )  # active | discarded | promoted
    category: Mapped[str] = mapped_column(String(128), default="", index=True)  # user/AI group
    cached_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_key_points: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    cached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
