"""Adding company documents (stored at once as "processing", then indexed in the background) and
deleting them.

TestClient runs background tasks before returning, so the final status is visible right after.
"""

import io
from pathlib import Path
from typing import Any

import docx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.main import app
from app.modules.knowledge import service
from app.modules.knowledge.models import Document, DocumentStatus
from app.modules.tenants import service as tenants_service

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _word(text: str) -> bytes:
    document = docx.Document()
    document.add_heading("Insurance", level=1)
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _documents(client: TestClient) -> dict[str, dict[str, Any]]:
    return {d["file_name"]: d for d in client.get("/knowledge").json()["documents"]}


def _search(query: str) -> list[str]:
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        return [p.document_name for p in service.search(session, tenant_id, query, k=3)]


def test_an_added_document_is_returned_processing_then_indexed(client: TestClient) -> None:
    content = _word("Accident insurance under UVG with Suva, policy SUVA-77-1234.")

    response = client.post(
        "/knowledge/documents", files=[("files", ("UVG certificate.docx", content, DOCX))]
    )

    assert response.status_code == 202
    [added] = response.json()
    assert added["name"] == "UVG certificate"
    assert added["status"] == "processing"
    assert added["indexed_at"] is None
    listed = _documents(client)
    assert len(listed) == 12
    assert listed["UVG certificate.docx"]["status"] == "indexed"
    assert "UVG certificate" in _search("SUVA-77-1234")
    file = client.get(f"/knowledge/documents/{added['id']}/file")
    assert file.content == content


def test_several_documents_can_be_added_at_once(client: TestClient) -> None:
    pdf = (get_settings().seed_knowledge_dir / "06_tax_attestation.pdf").read_bytes()

    response = client.post(
        "/knowledge/documents",
        files=[
            ("files", ("VAT statement.pdf", pdf, PDF)),
            ("files", ("Notes.docx", _word("Founded in Zurich."), DOCX)),
        ],
    )

    assert [d["file_name"] for d in response.json()] == ["VAT statement.pdf", "Notes.docx"]
    listed = _documents(client)
    assert listed["VAT statement.pdf"]["status"] == "indexed"
    assert listed["VAT statement.pdf"]["pages"] == 1
    assert listed["Notes.docx"]["status"] == "indexed"


def test_an_unreadable_file_ends_in_error_with_its_reason(client: TestClient) -> None:
    client.post("/knowledge/documents", files=[("files", ("scan.pdf", b"%PDF-1.7 junk", PDF))])

    scan = _documents(client)["scan.pdf"]

    assert scan["status"] == "error"
    assert scan["error"] == "This file is not a readable PDF."


def test_a_document_with_the_same_name_replaces_the_previous_one(client: TestClient) -> None:
    first = client.post(
        "/knowledge/documents",
        files=[("files", ("Insurance.docx", _word("Policy OLD-111 with Alpina."), DOCX))],
    ).json()[0]

    second = client.post(
        "/knowledge/documents",
        files=[("files", ("Insurance.docx", _word("Policy NEW-222 with Helvetia."), DOCX))],
    ).json()[0]

    assert second["id"] == first["id"]
    assert len(_documents(client)) == 12
    assert "Insurance" in _search("NEW-222 Helvetia")
    assert "Insurance" not in _search("OLD-111 Alpina")


@pytest.mark.parametrize(
    ("file_name", "content", "message"),
    [
        ("notes.txt", b"hello", "only PDF and Word (.docx) documents can be added"),
        ("old.doc", b"\xd0\xcf\x11\xe0", "only PDF and Word (.docx) documents can be added"),
        ("empty.pdf", b"", "empty.pdf is empty"),
    ],
)
def test_a_file_that_cannot_be_added_refuses_the_whole_request(
    client: TestClient, file_name: str, content: bytes, message: str
) -> None:
    response = client.post(
        "/knowledge/documents",
        files=[
            ("files", ("Notes.docx", _word("Founded in Zurich."), DOCX)),
            ("files", (file_name, content, "application/octet-stream")),
        ],
    )

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert len(_documents(client)) == 11


def test_a_file_too_large_is_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "MAX_FILE_BYTES", 10)

    response = client.post(
        "/knowledge/documents", files=[("files", ("big.pdf", b"%PDF-" + b"x" * 20, PDF))]
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "big.pdf is larger than 0 MB."


def test_a_request_without_files_is_refused(client: TestClient) -> None:
    assert client.post("/knowledge/documents").status_code == 422


def test_an_unexpected_failure_is_reported_on_the_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_content: bytes):
        raise RuntimeError("model crashed")

    monkeypatch.setitem(service.EXTRACTORS, service.DocumentFormat.DOCX, broken)

    client.post("/knowledge/documents", files=[("files", ("Notes.docx", _word("x"), DOCX))])

    notes = _documents(client)["Notes.docx"]
    assert notes["status"] == "error"
    assert notes["error"] == service.UNEXPECTED_ERROR


def test_documents_left_processing_are_indexed_at_the_next_start(
    client: TestClient, tmp_path: Path
) -> None:
    # A document stored, but the server stopped before indexing it.
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        [stored] = service.add_documents(
            session,
            tenant_id,
            [service.NewFile("Notes.docx", _word("Founded in Zurich."))],
            get_settings().data_dir,
        )
        assert session.get_one(Document, stored.id).status == DocumentStatus.PROCESSING

    with TestClient(app) as restarted:
        pass

    assert _documents(restarted)["Notes.docx"]["status"] == "indexed"


def test_deleting_a_document_removes_it_its_passages_and_its_file(client: TestClient) -> None:
    register = _documents(client)["01_commercial_register_extract.pdf"]
    with SessionLocal() as session:
        path = get_settings().data_dir / session.get_one(Document, register["id"]).file_path
    assert path.exists()

    response = client.delete(f"/knowledge/documents/{register['id']}")

    assert response.status_code == 204
    assert "01_commercial_register_extract.pdf" not in _documents(client)
    assert "Commercial register extract" not in _search("UID CHE-123.456.789")
    assert not path.exists()
    assert client.get(f"/knowledge/documents/{register['id']}/file").status_code == 404


def test_deleting_an_unknown_or_another_tenants_document_is_a_404(client: TestClient) -> None:
    assert client.delete("/knowledge/documents/999999").status_code == 404
    with SessionLocal() as session:
        other = tenants_service.ensure_tenant(session, slug="other", name="Other AG")
        session.commit()
        [theirs] = service.add_documents(
            session, other.id, [service.NewFile("Notes.docx", _word("x"))], get_settings().data_dir
        )

    assert client.delete(f"/knowledge/documents/{theirs.id}").status_code == 404


def test_a_document_deleted_before_its_indexing_is_skipped(client: TestClient) -> None:
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        [stored] = service.add_documents(
            session, tenant_id, [service.NewFile("Notes.docx", _word("x"))], get_settings().data_dir
        )
        service.delete_document(session, tenant_id, stored.id, get_settings().data_dir)

    service.index_documents([stored.id], get_settings().data_dir)

    assert "Notes.docx" not in _documents(client)
