"""Application configuration."""

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
    app_name: str = "Distillation"

    # Database (SQLite for MVP)
    database_url: str = "sqlite+aiosqlite:///./distillation.db"

    # LLM (OpenAI by default; set ANTHROPIC_API_KEY for Claude)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Content fetching
    fetch_timeout_seconds: float = 30.0
    max_content_length: int = 100_000


settings = Settings()
