"""Distillation FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import bookmarks, health, ingest
from app.config import settings
from app.core.logging import setup_logging
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup and shutdown."""
    setup_logging(debug=settings.debug)
    await init_db()
    yield
    # Shutdown: nothing to do


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(bookmarks.router)


def main() -> None:
    """CLI entry point."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
