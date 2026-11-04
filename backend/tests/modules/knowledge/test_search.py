"""Hybrid search with the deterministic test embedder (the real model: test_search_recall.py)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.knowledge import service
from app.modules.tenants import service as tenants_service


def _search(query: str, tenant_id: int | None = None, k: int = 8):
    with SessionLocal() as session:
        tenant = tenant_id or tenants_service.get_current_tenant_id(session)
        return service.search(session, tenant, query, k=k)


def test_an_identifier_finds_the_passage_that_holds_it(client: TestClient) -> None:
    [best, *_] = _search("UID CHE-123.456.789")

    assert best.document_name == "Commercial register extract"
    assert "CHE-123.456.789" in best.text
    assert best.page == 0


def test_results_come_best_first_and_at_most_k(client: TestClient) -> None:
    results = _search("liability insurance amount per claim", k=3)

    assert len(results) == 3
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert results[0].document_name == "Liability insurance certificate"


def test_the_section_heading_helps_find_a_word_passage(client: TestClient) -> None:
    results = _search("occupational health and safety")

    assert any(
        r.document_name == "Hr compliance policy" and "safety officer" in r.text for r in results
    )


def test_a_query_of_stop_words_only_still_returns_vector_matches(client: TestClient) -> None:
    assert len(_search("the of and", k=2)) == 2


def test_another_tenant_never_sees_these_documents(client: TestClient, tmp_path: Path) -> None:
    with SessionLocal() as session:
        other = tenants_service.ensure_tenant(session, slug="other", name="Other AG")
        session.commit()
        other_id = other.id

    assert _search("CHE-123.456.789", tenant_id=other_id) == []

    own = tmp_path / "other_register.pdf"
    own.write_bytes((get_settings().seed_knowledge_dir / "06_tax_attestation.pdf").read_bytes())
    with SessionLocal() as session:
        service.import_document(session, other_id, own, get_settings().data_dir)
        session.commit()

    assert {r.document_name for r in _search("tax", tenant_id=other_id)} == {"Other register"}
