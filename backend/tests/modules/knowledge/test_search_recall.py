"""Search recall with the real embedding model, against knowledge-base/GROUND_TRUTH.md.

The AI answers one form section at a time, from the passages found for each of its fields
(docs/ARCHITECTURE.md §3, Remplissage). So for each section, searching the labels of its fields
must bring, among all the passages found, the one holding each expected value: otherwise the AI
would answer "not found" although the answer is in the documents. Slow: loads the model.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.modules.knowledge import service
from app.modules.knowledge.embedding import FastEmbedder
from app.modules.tenants import service as tenants_service

pytestmark = pytest.mark.slow

K = 8

# Sections as the forms group their fields: {section: [(field label, text the passage holds)]}.
SECTIONS = {
    "Annex 7 — bidder": [
        ("Name and legal form", "Company limited by shares"),
        ("Business address", "Pfingstweidstrasse 31"),
        ("Contact person", "Marc Keller"),
        ("Telephone", "+41 44 555 01 20"),
        ("E-mail", "marc.keller@alpenlogic.example"),
    ],
    "Annex 4 — company": [
        ("Exact company name", "Alpenlogic AG"),
        ("Street, postcode, city, country", "Pfingstweidstrasse 31"),
        ("UID", "CHE-123.456.789"),
        ("Legal form", "Company limited by shares"),
        ("Legal form since", "14.03.2016"),
        ("Share capital", "CHF 500,000"),
        ("Main activity", "Digital strategy"),
        ("Certificates", "27001"),
    ],
    "Annex 4 — staff": [
        ("Employees with higher professional training", "14"),
        ("Employees with professional training", "9"),
    ],
    "Annex 4 — insurance": [
        ("Insurance company", "Limmat Versicherungen AG"),
        ("Amount per claim personal injury", "10,000,000"),
        ("Amount per claim financial loss", "5,000,000"),
    ],
    "Annex 4 — offices": [
        ("Competent tax office", "Steuerweg 12"),
        ("AHV compensation office", "Hardturmstrasse 120"),
        ("BVG pension fund", "Sammelstiftung Limmat BVG"),
    ],
    "Annex 4 — declarations": [
        ("Debt enforcement proceedings pending", "Debt collection proceedings"),
        ("Agreements restricting competition", "competition"),
        ("Occupational health and safety", "health and safety"),
    ],
}


@pytest.fixture
def real_model_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The app, its seed indexed with the real model."""
    embedder = FastEmbedder()
    monkeypatch.setattr(service, "get_embedder", lambda: embedder)
    with TestClient(app) as client:
        yield client


def test_each_sections_passages_hold_every_expected_value(real_model_client: TestClient) -> None:
    misses = []
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        for section, fields in SECTIONS.items():
            found = [
                passage.text.lower()
                for label, _ in fields
                for passage in service.search(session, tenant_id, label, k=K)
            ]
            misses += [
                (section, label, expected)
                for label, expected in fields
                if not any(expected.lower() in text for text in found)
            ]

    assert misses == []
