from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://tiyasha@/chitro?host=/var/run/postgresql"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    AUTH_SECRET_KEY: str = "development-only-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:3000"

    model_config = {
        "env_file": Path(__file__).resolve().parents[2] / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()


def get_cors_origins(value: str = settings.CORS_ORIGINS) -> list[str]:
    """Parse comma-separated allowed frontend origins, ignoring empty entries."""
    return [origin.strip() for origin in value.split(",") if origin.strip()]
