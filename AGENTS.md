# AGENTS.md

Read all `.cursor/rules/*.mdc` files for process, safety, and coding conventions.

---

## Project Context

### Overview

Distillation helps tame information overload by distilling bookmarks and web content into briefs and summaries. Ingest bookmark exports, fetch content, filter low-value items, and get AI-generated briefs.

### Goals

- [x] Phase 1: Bookmark export ingest (HTML/JSON), content fetch, direct distill to brief
- [ ] Phase 2: Interactive chat agent (MCP + Claude Desktop), more sources (news, blogs)
- [ ] Phase 3: n8n webhook, email newsletter integration

### Non-Goals

- Not a full bookmark manager (no sync with browser)
- Not building a general-purpose RAG system

### Technical Constraints

- Deployment: Standalone (HTTP API) + n8n (HTTP Request node) + MCP (Claude Desktop)
- Database: SQLite for MVP
- LLM: Gemini (gemini-2.5-flash) via Instructor for structured outputs
- MCP: FastMCP for Claude Desktop integration

### Domain Context

- **Bookmark export**: Netscape HTML (Chrome/Firefox) or Chrome JSON
- **Content extraction**: Fetch + minimal strip; AI (Gemini) extracts and summarizes
- **Brief**: Structured overview + per-item summaries, key points, keep/discard
- **Interactive mode**: Chat with Claude via MCP tools (list, distill, summarize, discard)

---

## Code Patterns

# AGENTS.md — Python (Base)

Cross-platform instructions for AI coding agents.
Works with: Claude Code, Cursor, Windsurf, Gemini, ChatGPT, GitHub Copilot.

---

## Quick Reference

```yaml
Runtime:     Python 3.12+ (via UV)
Validation:  Pydantic v2
Logging:     structlog + Rich
Testing:     pytest + pytest-asyncio + Hypothesis
Linting:     Ruff (lint + format)
Types:       Pyright
Git Hooks:   Lefthook (parallel, YAML config)
Tasks:       Just
Debugging:   icecream + ipdb
```

---

## Commands (Shared)

```bash
# Environment
uv sync                    # Install dependencies
uv run python app.py       # Run with project environment
uv add package             # Add dependency
uv add --dev package       # Add dev dependency

# Quality
just check                 # Run all checks (lint, type, test)
just lint                  # Ruff lint
just format                # Ruff format
just typecheck             # Pyright type check

# Testing
just test                  # Run tests
just test-cov              # Run tests with coverage
just test-watch            # Run tests in watch mode
```

---

## Pydantic Schema

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base user schema with shared fields."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(min_length=8)


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Schema for updating a user (all fields optional)."""

    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
```

---

## Configuration (Pydantic Settings)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    debug: bool = False
    app_name: str = "My API"

    # Database
    database_url: str

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 30


settings = Settings()
```

---

## Logging (structlog + Rich)

```python
import logging
import structlog

def setup_logging(debug: bool = False) -> None:
    """Configure structlog with Rich for beautiful console output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage
log = structlog.get_logger()
log.info("server_started", port=8000, env="production")
log.error("request_failed", error=str(e), request_id=req_id)
```

---

## Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st, settings
import pytest

# Basic property test
@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs: list[int]) -> None:
    """Sorting twice gives same result as sorting once."""
    assert sorted(sorted(xs)) == sorted(xs)


# Test with custom strategies
@given(
    email=st.emails(),
    name=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))),
)
def test_user_create_schema_validates(email: str, name: str) -> None:
    """UserCreate schema accepts valid inputs."""
    from app.schemas.user import UserCreate
    user = UserCreate(email=email, name=name, password="validpassword123")
    assert user.email == email


# Async property test
@pytest.mark.asyncio
@given(user_id=st.integers(min_value=1))
@settings(max_examples=50)  # Limit examples for async tests
async def test_get_nonexistent_user_returns_none(db_session, user_id: int) -> None:
    """Getting a non-existent user returns None."""
    from app.services.user import UserService
    service = UserService(db_session)
    result = await service.get_by_id(user_id)
    assert result is None
```

---

## Debugging with icecream

```python
from icecream import ic

# Instead of print debugging
def process_order(order: Order) -> Result:
    ic(order.id, order.status)  # ic| order.id: 42, order.status: 'pending'

    total = calculate_total(order.items)
    ic(total)  # ic| total: 159.99

    if total > 100:
        ic("applying discount")  # ic| 'applying discount'
        total *= 0.9

    return Result(total=total)

# Disable in production
import os
if os.getenv("ENV") == "production":
    ic.disable()
```

---

## Type Hints

### Standard Library Types

```python
from collections.abc import Callable, Sequence, Mapping, AsyncGenerator
from typing import Any, TypeVar, Generic

# Use | for unions (Python 3.10+)
def process(value: str | None) -> str | None: ...

# Use lowercase for built-in types (Python 3.9+)
def get_items() -> list[str]: ...
def get_mapping() -> dict[str, int]: ...
```

### Generic Types

```python
from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    page: int
    page_size: int
```

---

## Error Handling

### Custom Exceptions

```python
# app/core/errors.py

class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found", "NOT_FOUND")


class ValidationError(AppError):
    """Validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR")
```

---

## File Naming

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case | `user_service.py`, `auth_utils.py` |
| Classes | PascalCase | `class UserService:`, `class AuthToken:` |
| Functions | snake_case | `def get_user_by_id():` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES = 3`, `API_VERSION = "v1"` |
| Type Variables | PascalCase | `T = TypeVar("T")` |

---

## Stack Reference

See the Python STACK.md and STYLE.md for full technology choices.

---

# FastAPI

---

## Quick Reference

```yaml
Framework:   FastAPI + Uvicorn
Database:    SQLAlchemy 2.0 + asyncpg + Atlas
Agents:      PydanticAI + Instructor
```

---

## Commands

```bash
# Development
just dev                   # Start dev server
just shell                 # Open Python shell with env

# Database
just db-migrate            # Run migrations
just db-upgrade            # Generate + run migrations
just db-downgrade          # Rollback one migration
```

---

## Project Structure

```
src/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Settings via pydantic-settings
│   ├── deps.py            # Dependency injection
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/        # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   └── users.py
│   │   └── deps.py        # Route-specific dependencies
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py    # Auth utilities
│   │   └── errors.py      # Custom exceptions
│   ├── models/            # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/           # Pydantic schemas
│   │   ├── __init__.py
│   │   └── user.py
│   ├── services/          # Business logic
│   │   ├── __init__.py
│   │   └── user.py
│   └── db/
│       ├── __init__.py
│       ├── session.py     # Database connection
│       └── schema.sql     # Atlas schema (or migrations/)
tests/
├── conftest.py            # Shared fixtures
├── test_api/
└── test_services/
```

---

## FastAPI Route

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user import UserCreate, UserResponse
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user."""
    service = UserService(db)
    user = await service.create(data)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get user by ID."""
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)
```

---

## SQLAlchemy Model

```python
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """User database model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

---

## Service Layer

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password


class UserService:
    """User business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=data.email,
            name=data.name,
            hashed_password=hash_password(data.password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

---

## Database Session

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

---

## Test Fixture

```python
# tests/conftest.py
import pytest
from collections.abc import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

---

## Exception Handler

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.core.errors import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
```

---

## PydanticAI Agent Pattern

```python
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from httpx import AsyncClient

class Dependencies(BaseModel):
    """Dependencies injected into agent tools."""
    http_client: AsyncClient
    api_key: str

class WeatherResult(BaseModel):
    """Structured output from weather agent."""
    location: str
    temperature: float
    conditions: str

weather_agent = Agent(
    "openai:gpt-4o",
    deps_type=Dependencies,
    result_type=WeatherResult,
    system_prompt="You are a weather assistant. Use the get_weather tool to fetch data.",
)

@weather_agent.tool
async def get_weather(ctx: RunContext[Dependencies], location: str) -> str:
    """Fetch weather data for a location."""
    response = await ctx.deps.http_client.get(
        f"https://api.weather.com/v1/current",
        params={"q": location, "key": ctx.deps.api_key},
    )
    return response.text

# Usage
async def main():
    async with AsyncClient() as client:
        deps = Dependencies(http_client=client, api_key="...")
        result = await weather_agent.run("What's the weather in Tokyo?", deps=deps)
        print(result.data)  # WeatherResult(location="Tokyo", ...)
```

---

## Critical Rules (FastAPI)

### Always

- Use `async def` for route handlers and database operations
- Use dependency injection via `Depends()`

### Never

- Use `time.sleep()` in async code — use `asyncio.sleep()`
