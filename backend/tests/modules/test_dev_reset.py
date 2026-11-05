"""POST /dev/reset: back to the start of the demo, only when the development helpers are on."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.modules.helpers import demo_document, fields_by_key, seeded_forms

PDF = "application/pdf"


@pytest.fixture
def dev_tools(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("FORMPILOT_DEV_TOOLS", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def test_reset_is_404_when_the_dev_tools_are_off(client: TestClient) -> None:
    assert client.post("/dev/reset").status_code == 404


def test_reset_deletes_the_documents_and_every_answer(client: TestClient, dev_tools: None) -> None:
    source = demo_document("03_liability_insurance_certificate.pdf")
    client.post("/knowledge/documents", files=[("files", (source.name, source.read_bytes(), PDF))])
    annex_7 = seeded_forms(client)[1]["id"]
    telephone = fields_by_key(client, annex_7)["telephone"]
    client.patch(f"/forms/{annex_7}/fields/{telephone['id']}", json={"value": "044"})
    assert seeded_forms(client)[1]["status"] != "not_started"

    assert client.post("/dev/reset").status_code == 204

    assert client.get("/knowledge").json()["documents"] == []
    for form in seeded_forms(client):
        assert form["status"] == "not_started"
        assert client.get(f"/forms/{form['id']}/answers").json()["answers"] == []
