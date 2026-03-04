"""Database session and connection."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base


# Ensure SQLite uses aiosqlite for async
_db_url = settings.database_url
if _db_url.startswith("sqlite://") and "aiosqlite" not in _db_url:
    _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Resolve relative SQLite paths to absolute (project root) so DB works when cwd differs
if _db_url.startswith("sqlite") and ":///./" in _db_url:
    _rel_path = _db_url.split(":///./", 1)[1]
    _project_root = Path(__file__).resolve().parent.parent.parent
    _abs_path = (_project_root / _rel_path).resolve()
    _abs_path.parent.mkdir(parents=True, exist_ok=True)
    _db_url = _db_url.replace(f":///./{_rel_path}", f":///{_abs_path}", 1)

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    pool_pre_ping=not _db_url.startswith("sqlite"),
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables and run migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_add_bookmark_status)
        await conn.run_sync(_migrate_add_group_and_cache)
        await conn.run_sync(_migrate_status_values)


def _migrate_add_bookmark_status(conn: "Connection") -> None:
    """Add status column to bookmarks if it doesn't exist."""
    from sqlalchemy import text

    result = conn.execute(text("PRAGMA table_info(bookmarks)"))
    columns: list[str] = [row[1] for row in result.fetchall()]
    if "status" not in columns:
        conn.execute(text("ALTER TABLE bookmarks ADD COLUMN status VARCHAR(32) DEFAULT 'active'"))


def _migrate_add_group_and_cache(conn: "Connection") -> None:
    """Add group and cache columns if missing."""
    from sqlalchemy import text

    result = conn.execute(text("PRAGMA table_info(bookmarks)"))
    columns: list[str] = [row[1] for row in result.fetchall()]
    if "category" not in columns:
        conn.execute(text("ALTER TABLE bookmarks ADD COLUMN category VARCHAR(128) DEFAULT ''"))
    if "cached_summary" not in columns:
        conn.execute(text("ALTER TABLE bookmarks ADD COLUMN cached_summary TEXT"))
    if "cached_key_points" not in columns:
        conn.execute(text("ALTER TABLE bookmarks ADD COLUMN cached_key_points TEXT"))
    if "cached_at" not in columns:
        conn.execute(text("ALTER TABLE bookmarks ADD COLUMN cached_at DATETIME"))


def _migrate_status_values(conn: "Connection") -> None:
    """Migrate status: active->unreviewed, discarded->discard, promoted->view."""
    from sqlalchemy import text

    conn.execute(text("UPDATE bookmarks SET status = 'unreviewed' WHERE status = 'active'"))
    conn.execute(text("UPDATE bookmarks SET status = 'discard' WHERE status = 'discarded'"))
    conn.execute(text("UPDATE bookmarks SET status = 'view' WHERE status = 'promoted'"))


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency for database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
