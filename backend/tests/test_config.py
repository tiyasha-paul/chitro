"""Deployment-oriented configuration tests."""

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        ("postgresql+psycopg://user:password@host/database", "postgresql+asyncpg://user:password@host/database"),
        ("postgresql://user:password@host/database", "postgresql+asyncpg://user:password@host/database"),
        ("postgres://user:password@host/database", "postgresql+asyncpg://user:password@host/database"),
        ("postgresql+asyncpg://user:password@host/database", "postgresql+asyncpg://user:password@host/database"),
    ],
)
def test_database_url_uses_asyncpg_driver(database_url: str, expected: str):
    assert Settings(DATABASE_URL=database_url).DATABASE_URL == expected
