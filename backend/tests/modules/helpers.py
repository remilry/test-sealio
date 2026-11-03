from typing import Any

from fastapi.testclient import TestClient


def seeded_forms(client: TestClient) -> list[dict[str, Any]]:
    """[Annex 4, Annex 7] summaries of the seeded tender."""
    [tender] = client.get("/tenders").json()
    return client.get(f"/tenders/{tender['id']}").json()["forms"]


def fields_by_key(client: TestClient, form_id: int) -> dict[str, dict[str, Any]]:
    return {field["key"]: field for field in client.get(f"/forms/{form_id}").json()["fields"]}
