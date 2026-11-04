from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.knowledge import service
from app.modules.tenants import service as tenants_service
from tests.modules.helpers import demo_document


def test_the_knowledge_base_starts_empty(empty_client: TestClient) -> None:
    knowledge = empty_client.get("/knowledge").json()

    assert knowledge == {"company_name": "Alpenlogic AG", "documents": [], "last_indexed_at": None}


def test_added_company_documents_are_listed_and_indexed(client: TestClient) -> None:
    knowledge = client.get("/knowledge").json()

    assert knowledge["company_name"] == "Alpenlogic AG"
    documents = knowledge["documents"]
    assert len(documents) == 11
    assert {d["status"] for d in documents} == {"indexed"}
    assert knowledge["last_indexed_at"] is not None
    register = next(d for d in documents if d["file_name"] == "01_commercial_register_extract.pdf")
    assert register["name"] == "Commercial register extract"
    assert register["file_format"] == "pdf"
    assert register["pages"] == 2
    assert register["error"] is None
    annual_report = next(d for d in documents if d["file_name"] == "09_annual_report_2024.docx")
    assert annual_report["file_format"] == "docx"
    assert annual_report["pages"] is None


def test_documents_are_kept_across_a_restart(client: TestClient) -> None:
    with TestClient(client.app):
        pass

    assert len(client.get("/knowledge").json()["documents"]) == 11


def test_an_unreadable_file_is_listed_with_its_error(client: TestClient, tmp_path: Path) -> None:
    broken = tmp_path / "scan_of_the_insurance_policy.pdf"
    broken.write_bytes(b"%PDF-1.7 truncated")
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        service.import_document(session, tenant_id, broken, get_settings().data_dir)
        session.commit()

    [newest, *_] = client.get("/knowledge").json()["documents"]

    assert newest["file_name"] == "scan_of_the_insurance_policy.pdf"
    assert newest["name"] == "Scan of the insurance policy"
    assert newest["status"] == "error"
    assert newest["error"] == "This file is not a readable PDF."
    assert newest["indexed_at"] is None


def test_a_document_file_is_served_as_uploaded(client: TestClient) -> None:
    document = client.get("/knowledge").json()["documents"][0]

    response = client.get(f"/knowledge/documents/{document['id']}/file")

    assert response.status_code == 200
    source = demo_document(document["file_name"])
    assert response.content == source.read_bytes()


def test_an_unknown_document_file_is_a_404(client: TestClient) -> None:
    assert client.get("/knowledge/documents/999999/file").status_code == 404


def test_display_names_come_from_the_file_name() -> None:
    assert service.display_name("04_company_brochure_2026.pdf") == "Company brochure 2026"
    assert service.display_name("ISO-27001 certificate.pdf") == "ISO 27001 certificate"
    assert service.display_name("2025.pdf") == "2025"
