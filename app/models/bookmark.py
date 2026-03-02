"""Bookmark model."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
