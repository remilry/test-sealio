from fastapi.testclient import TestClient

from tests.modules.helpers import seeded_forms


def test_tender_cards_show_what_was_detected_in_each_form(client: TestClient) -> None:
    annex_4, annex_7 = seeded_forms(client)

    assert annex_4["field_counts"] == {"fields": 49, "yes_no": 17, "signatures": 1}
    assert annex_7["field_counts"] == {"fields": 10, "yes_no": 0, "signatures": 1}


def test_form_detail_lists_the_fields_in_reading_order(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)

    form = client.get(f"/forms/{annex_7['id']}").json()

    assert form["title"] == "Annex 7 — Sanctions self-declaration (Art. 29c)"
    assert form["file_format"] == "pdf"
    assert form["tender_id"] > 0
    assert [(round(p["width"]), round(p["height"])) for p in form["pages"]] == [(595, 842)]
    assert [(f["label"], f["kind"]) for f in form["fields"]] == [
        ("Project number/project title/project name", "text"),
        ("Name of the contracting authority", "text"),
        ("Name and legal form", "text"),
        ("Business address", "text"),
        ("Contact person", "text"),
        ("Telephone", "text"),
        ("E-mail", "text"),
        ("Place and date", "text"),
        ("First name(s) and surname(s)", "text"),
        ("Signature(s)", "signature"),
    ]
    locator = form["fields"][0]["locator"]
    assert locator["format"] == "pdf"
    assert set(locator) == {"format", "page", "box", "baseline", "font_size", "erase"}


def test_a_word_form_is_parsed_at_seed(client: TestClient) -> None:
    annex_4, _ = seeded_forms(client)

    form = client.get(f"/forms/{annex_4['id']}").json()

    assert form["file_format"] == "docx"
    assert len(form["fields"]) == 49
    assert {f["locator"]["format"] for f in form["fields"]} == {"docx"}
    assert [(round(p["width"]), round(p["height"])) for p in form["pages"]] == [(595, 842)] * 3


def test_unknown_form_is_a_404(client: TestClient) -> None:
    assert client.get("/forms/999999").status_code == 404
