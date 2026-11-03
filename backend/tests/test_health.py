from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine


def test_health_reports_the_database_as_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_migrations_enable_pgvector() -> None:
    with engine.connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()

    assert version is not None
