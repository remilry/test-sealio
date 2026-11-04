"""Tests run against a dedicated PostgreSQL database, created and migrated once per session."""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

TEST_DB = "formpilot_test"
_base_url = make_url(
    os.environ.get(
        "FORMPILOT_DATABASE_URL",
        "postgresql+psycopg://formpilot:formpilot@localhost:5432/formpilot",
    )
)
TEST_DATABASE_URL = _base_url.set(database=TEST_DB).render_as_string(hide_password=False)
# Must be set before `app` is imported: the engine reads it at import time.
os.environ["FORMPILOT_DATABASE_URL"] = TEST_DATABASE_URL
# Deterministic embeddings: only the tests marked `slow` load the real model.
os.environ["FORMPILOT_EMBEDDER"] = "hash"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, engine  # noqa: E402
from app.core.migrations import upgrade_to_head  # noqa: E402
from app.main import app  # noqa: E402


def _create_test_database() -> None:
    admin = _base_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{TEST_DB}"')


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    _create_test_database()
    upgrade_to_head(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Uploads and copied forms go to a temporary folder, never to the repo's data/."""
    path = tmp_path_factory.mktemp("data")
    previous = os.environ.get("FORMPILOT_DATA_DIR")
    os.environ["FORMPILOT_DATA_DIR"] = str(path)
    get_settings.cache_clear()
    yield path
    if previous is None:
        os.environ.pop("FORMPILOT_DATA_DIR")
    else:
        os.environ["FORMPILOT_DATA_DIR"] = previous
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _empty_tables(database: None) -> Iterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if tables:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
