"""Database session and connection."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base


# Ensure SQLite uses aiosqlite for async
_db_url = settings.database_url
if _db_url.startswith("sqlite://") and "aiosqlite" not in _db_url:
    _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

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
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
