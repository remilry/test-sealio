"""Tests run against a dedicated PostgreSQL database, created and migrated once per session."""

import os
from collections.abc import Iterator

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

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

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
