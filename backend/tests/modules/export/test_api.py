import io
from collections.abc import Iterator

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.modules.forms import service as forms_service
from app.modules.forms.models import FileFormat
from app.modules.forms.parsing.docx_parser import parse_docx
from tests.modules.helpers import fields_by_key, seeded_forms

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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


@pytest.fixture
def word_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The app with Word forms parsed at seed (the app registers the parser in step 6b)."""
    monkeypatch.setitem(forms_service.PARSERS, FileFormat.DOCX, parse_docx)
    with TestClient(app) as test_client:
        yield test_client


def test_a_word_form_is_exported_as_word_under_its_original_name(word_client: TestClient) -> None:
    annex_4, _ = seeded_forms(word_client)
    _fill(word_client, annex_4["id"], {"exact_company_name": "Alpenlogic AG", "uid": "CHE-123"})

    response = word_client.get(f"/forms/{annex_4['id']}/export/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX_MEDIA_TYPE
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''"
        "Annex_4_Conditions%20of%20Participation%20and%20Company%20Self-Declaration.docx"
    )
    identity = Document(io.BytesIO(response.content)).tables[1]
    assert identity.cell(0, 1).text == "Alpenlogic AG"
    assert identity.cell(4, 1).text == "CHE-123"


def test_a_word_form_summary_lists_its_empty_fields_and_signature(word_client: TestClient) -> None:
    annex_4, _ = seeded_forms(word_client)
    _fill(word_client, annex_4["id"], {"exact_company_name": "Alpenlogic AG"})

    summary = word_client.get(f"/forms/{annex_4['id']}/export").json()

    assert summary["file_format"] == "docx"
    assert (summary["fillable"], summary["filled"]) == (48, 1)
    assert len(summary["empty_fields"]) == 47
    assert [f["label"] for f in summary["sign_by_hand"]] == [
        "Company stamp and legally valid signature(s)"
    ]


def test_unknown_form_export_is_a_404(client: TestClient) -> None:
    assert client.get("/forms/999999/export").status_code == 404
    assert client.get("/forms/999999/export/file").status_code == 404
