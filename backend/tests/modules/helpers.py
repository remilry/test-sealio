from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionLocal
from app.modules.knowledge import service as knowledge_service
from app.modules.knowledge.embedding import Embedder
from app.modules.tenants import service as tenants_service

# The demo company's documents (Alpenlogic AG, see knowledge-base/GROUND_TRUTH.md). Not seeded:
# a user adds them, so do the tests that need them.
DEMO_DOCUMENTS = REPO_ROOT / "knowledge-base" / "documents"


def seeded_forms(client: TestClient) -> list[dict[str, Any]]:
    """[Annex 4, Annex 7] summaries of the seeded tender."""
    [tender] = client.get("/tenders").json()
    return client.get(f"/tenders/{tender['id']}").json()["forms"]


def fields_by_key(client: TestClient, form_id: int) -> dict[str, dict[str, Any]]:
    return {field["key"]: field for field in client.get(f"/forms/{form_id}").json()["fields"]}


def add_demo_documents(embedder: Embedder | None = None) -> None:
    """Add and index the 11 demo documents for the current tenant (the app must have started)."""
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        for source in sorted(DEMO_DOCUMENTS.glob("*")):
            if source.suffix.lower() in {".pdf", ".docx"}:
                knowledge_service.import_document(
                    session, tenant_id, source, get_settings().data_dir, embedder
                )
        session.commit()


def demo_document(file_name: str) -> Path:
    return DEMO_DOCUMENTS / file_name
