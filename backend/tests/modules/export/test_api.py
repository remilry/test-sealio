import pymupdf
from fastapi.testclient import TestClient

from tests.modules.helpers import fields_by_key, seeded_forms


def _fill(client: TestClient, form_id: int, values: dict[str, str]) -> None:
    fields = fields_by_key(client, form_id)
    for key, value in values.items():
        url = f"/forms/{form_id}/fields/{fields[key]['id']}"
        response = client.patch(url, json={"value": value})
        assert response.status_code == 200


def test_summary_lists_empty_fields_and_what_to_sign_by_hand(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    _fill(client, annex_7["id"], {"name_and_legal_form": "Alpenlogic AG", "telephone": "044"})

    summary = client.get(f"/forms/{annex_7['id']}/export").json()

    assert summary["file_format"] == "pdf"
    assert (summary["fillable"], summary["filled"]) == (9, 2)
    assert [f["label"] for f in summary["empty_fields"]] == [
        "Project number/project title/project name",
        "Name of the contracting authority",
        "Business address",
        "Contact person",
        "E-mail",
        "Place and date",
        "First name(s) and surname(s)",
    ]
    assert [f["label"] for f in summary["sign_by_hand"]] == ["Signature(s)"]


def test_downloads_the_filled_pdf_with_the_original_name(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    _fill(client, annex_7["id"], {"name_and_legal_form": "Alpenlogic AG", "telephone": "044"})

    response = client.get(f"/forms/{annex_7['id']}/export/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"
    )
    with pymupdf.open(stream=response.content, filetype="pdf") as doc:
        text = doc[0].get_text()
    assert "Alpenlogic AG" in text
    assert "044" in text


def test_a_word_form_cannot_be_exported_yet(client: TestClient) -> None:
    annex_4, _ = seeded_forms(client)

    response = client.get(f"/forms/{annex_4['id']}/export/file")

    assert response.status_code == 422


def test_unknown_form_export_is_a_404(client: TestClient) -> None:
    assert client.get("/forms/999999/export").status_code == 404
    assert client.get("/forms/999999/export/file").status_code == 404
