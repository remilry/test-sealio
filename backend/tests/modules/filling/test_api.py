from fastapi.testclient import TestClient

from tests.modules.helpers import fields_by_key, seeded_forms


def test_a_new_form_has_no_answers_and_everything_to_fill(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)

    state = client.get(f"/forms/{annex_7['id']}/answers").json()

    # 10 fields, the signature excluded.
    assert state == {"counts": {"fillable": 9, "filled": 0, "empty": 9}, "answers": []}


def test_saving_a_value_records_it_as_entered_by_the_user(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]

    response = client.patch(
        f"/forms/{annex_7['id']}/fields/{telephone['id']}", json={"value": " +41 44 512 38 00 "}
    )

    assert response.status_code == 200
    state = response.json()
    assert state["counts"] == {"fillable": 9, "filled": 1, "empty": 8}
    [answer] = state["answers"]
    assert answer["field_id"] == telephone["id"]
    assert answer["value"] == "+41 44 512 38 00"
    assert answer["resolved_by"] == "user"
    assert client.get(f"/forms/{annex_7['id']}/answers").json() == state


def test_the_form_is_in_review_once_a_value_is_saved(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]

    client.patch(f"/forms/{annex_7['id']}/fields/{telephone['id']}", json={"value": "044"})

    assert seeded_forms(client)[1]["status"] == "in_review"


def test_changing_then_clearing_a_value(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    e_mail = fields_by_key(client, annex_7["id"])["e_mail"]
    url = f"/forms/{annex_7['id']}/fields/{e_mail['id']}"

    client.patch(url, json={"value": "info@alpenlogic.ch"})
    changed = client.patch(url, json={"value": "tenders@alpenlogic.ch"}).json()
    cleared = client.patch(url, json={"value": "   "}).json()

    assert [a["value"] for a in changed["answers"]] == ["tenders@alpenlogic.ch"]
    assert [a["value"] for a in cleared["answers"]] == [None]
    assert cleared["counts"]["filled"] == 0


def test_a_signature_is_never_filled(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    signature = fields_by_key(client, annex_7["id"])["signature_s"]

    response = client.patch(
        f"/forms/{annex_7['id']}/fields/{signature['id']}", json={"value": "Marc Keller"}
    )

    assert response.status_code == 422
    assert "sign" in response.json()["detail"]
    assert client.get(f"/forms/{annex_7['id']}/answers").json()["answers"] == []


def test_a_field_of_another_form_is_a_404(client: TestClient) -> None:
    annex_4, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]

    response = client.patch(
        f"/forms/{annex_4['id']}/fields/{telephone['id']}", json={"value": "044"}
    )

    assert response.status_code == 404


def test_answers_of_an_unknown_form_is_a_404(client: TestClient) -> None:
    assert client.get("/forms/999999/answers").status_code == 404
