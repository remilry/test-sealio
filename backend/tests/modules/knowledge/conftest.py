from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.modules.helpers import add_demo_documents


@pytest.fixture
def client() -> Iterator[TestClient]:
    """The app with the demo company's 11 documents added, as a user would (they are not seeded)."""
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client


@pytest.fixture
def empty_client() -> Iterator[TestClient]:
    """The app as it starts: an empty knowledge base."""
    with TestClient(app) as test_client:
        yield test_client
