from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.filling import service as filling_service
from app.modules.tenants import service as tenants_service
from app.seed import seed
from tests.modules.helpers import seeded_forms

ANNEX_4 = "Annex_4_Conditions of Participation and Company Self-Declaration.docx"
ANNEX_7 = "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"


def test_lists_the_seeded_tender(client: TestClient) -> None:
    response = client.get("/tenders")

    assert response.status_code == 200
    [tender] = response.json()
    assert tender["reference"] == "ZH-2026-0412"
    assert tender["title"] == "Cloud Platform Services – Canton of Zurich"
    assert tender["submission_deadline"] == "2026-11-19"


def test_tender_detail_lists_both_annexes_in_order_and_not_started(client: TestClient) -> None:
    [summary] = client.get("/tenders").json()

    tender = client.get(f"/tenders/{summary['id']}").json()

    assert tender["procedure"] == "Open procedure"
    assert tender["authority"] == "Canton of Zurich, Office for Information Technology"
    assert [(f["file_name"], f["file_format"], f["status"]) for f in tender["forms"]] == [
        (ANNEX_4, "docx", "not_started"),
        (ANNEX_7, "pdf", "not_started"),
    ]


def test_unknown_tender_is_a_404(client: TestClient) -> None:
    response = client.get("/tenders/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender 999999 not found"}


def test_seeding_twice_changes_nothing(client: TestClient) -> None:
    before = client.get("/tenders").json()
    tender_before = client.get(f"/tenders/{before[0]['id']}").json()

    with SessionLocal() as session:
        seed(session, get_settings())

    assert client.get("/tenders").json() == before
    assert client.get(f"/tenders/{before[0]['id']}").json() == tender_before


def test_downloads_each_original_form_unchanged(client: TestClient) -> None:
    [summary] = client.get("/tenders").json()
    forms = client.get(f"/tenders/{summary['id']}").json()["forms"]
    expected_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    for form in forms:
        response = client.get(f"/forms/{form['id']}/file")

        assert response.status_code == 200
        assert response.headers["content-type"] == expected_types[form["file_format"]]
        original = get_settings().seed_forms_dir / form["file_name"]
        assert response.content == original.read_bytes()


def test_unknown_form_file_is_a_404(client: TestClient) -> None:
    assert client.get("/forms/999999/file").status_code == 404


def test_cards_estimate_the_fill_duration_from_the_sections(client: TestClient) -> None:
    annex_4, annex_7 = seeded_forms(client)

    # One section, 25 seconds each; a form that is not parsed has no estimate.
    assert annex_7["estimated_fill_seconds"] == 25
    assert annex_4["estimated_fill_seconds"] is None
    assert client.get(f"/forms/{annex_7['id']}").json()["estimated_fill_seconds"] == 25


def test_a_card_says_when_the_form_is_being_filled(client: TestClient) -> None:
    annex_7 = seeded_forms(client)[1]
    assert annex_7["filling"] is False

    with SessionLocal() as session:
        filling_service.start_ai_fill(
            session, tenants_service.get_current_tenant_id(session), annex_7["id"]
        )

    assert seeded_forms(client)[1]["filling"] is True
