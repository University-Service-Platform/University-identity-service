"""DATABASE_URL handling for hosted Postgres (e.g. Render) and local SQLite."""
import pytest

from app.core.config import database_url_for


@pytest.mark.parametrize("given", [
    "postgres://identity:secret@dpg-abc123-a/identity",      # legacy scheme, rejected by SQLAlchemy 2
    "postgresql://identity:secret@dpg-abc123-a/identity",    # Render's connection string
])
def test_postgres_urls_are_pinned_to_the_psycopg_driver(given):
    assert database_url_for(given) == "postgresql+psycopg://identity:secret@dpg-abc123-a/identity"


@pytest.mark.parametrize("given", [
    "sqlite:///./identity.db",
    "postgresql+psycopg://identity:secret@localhost/identity",   # driver already chosen
])
def test_other_urls_are_left_unchanged(given):
    assert database_url_for(given) == given
