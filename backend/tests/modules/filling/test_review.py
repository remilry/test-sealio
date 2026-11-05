"""Review: the user settles doubts and empty fields; what is left open; the ready status."""

from typing import Any

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.modules.filling import service
from app.modules.filling.models import AiStatus
from app.modules.filling.rules import AnswerType, Decision
from app.modules.filling.validator import Candidate, Citation
from app.modules.tenants import service as tenants_service
from tests.modules.helpers import fields_by_key, seeded_forms


def candidate(value: str) -> Candidate:
    citation = Citation(
        quote=value, document_name="Register.pdf", document_id=None, chunk_id=None, page=0
    )
    return Candidate(value=value, citations=[citation])


def ai_answers(
    client: TestClient, form_id: int, answers: dict[str, tuple[AnswerType, str | None]]
) -> dict[str, int]:
    """Record a finished automatic fill with these answers (by field key); returns the field ids.

    A conflict gets two candidates: the value and "<value> (other)".
    """
    fields = fields_by_key(client, form_id)
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        fill_id = service.start_ai_fill(session, tenant_id, form_id)
        for key, (answer_type, value) in answers.items():
            candidates = [] if value is None else [candidate(value)]
            if answer_type == AnswerType.CONFLICT and value is not None:
                candidates.append(candidate(f"{value} (other)"))
            service.record_ai_answer(
                session, fill_id, fields[key]["id"], Decision(answer_type, value, candidates)
            )
        service.finish_ai_fill(session, fill_id, AiStatus.DONE)
        session.commit()
    return {key: fields[key]["id"] for key in answers}


def answer_of(client: TestClient, form_id: int, field_id: int) -> dict[str, Any]:
    state = client.get(f"/forms/{form_id}/answers").json()
    return next(a for a in state["answers"] if a["field_id"] == field_id)


def annex_7(client: TestClient) -> int:
    return seeded_forms(client)[1]["id"]


def test_an_automatic_answer_remembers_the_value_it_proposed(client: TestClient) -> None:
    form_id = annex_7(client)
    ids = ai_answers(client, form_id, {"telephone": (AnswerType.OUTDATED, "+41 44 512 38 00")})

    answer = answer_of(client, form_id, ids["telephone"])

    assert answer["proposed_value"] == "+41 44 512 38 00"
    assert answer["resolved_by"] == "ai"


def test_the_proposed_value_stays_when_the_user_changes_or_clears_it(client: TestClient) -> None:
    form_id = annex_7(client)
    ids = ai_answers(client, form_id, {"telephone": (AnswerType.OUTDATED, "+41 44 512 38 00")})
    url = f"/forms/{form_id}/fields/{ids['telephone']}"

    client.patch(url, json={"value": "+41 44 000 00 00"})
    changed = answer_of(client, form_id, ids["telephone"])
    client.patch(url, json={"value": None})
    cleared = answer_of(client, form_id, ids["telephone"])

    assert (changed["value"], changed["proposed_value"], changed["type"]) == (
        "+41 44 000 00 00",
        "+41 44 512 38 00",
        "outdated",
    )
    assert (cleared["value"], cleared["proposed_value"]) == (None, "+41 44 512 38 00")


def test_a_value_entered_by_hand_has_no_proposed_value(client: TestClient) -> None:
    form_id = annex_7(client)
    telephone = fields_by_key(client, form_id)["telephone"]["id"]

    client.patch(f"/forms/{form_id}/fields/{telephone}", json={"value": "044"})

    assert answer_of(client, form_id, telephone)["proposed_value"] is None


ANNEX_7_DOUBTS = {
    "name_and_legal_form": (AnswerType.CONFLICT, "Alpenlogic AG"),
    "telephone": (AnswerType.OUTDATED, "+41 44 512 38 00"),
    "place_and_date": (AnswerType.MANUAL, "Zurich, 05.11.2026"),
    "e_mail": (AnswerType.AUTO, "info@alpenlogic.ch"),
    "first_name_s_and_surname_s": (AnswerType.MISSING, None),
}


def counts(client: TestClient, form_id: int) -> dict[str, int]:
    return client.get(f"/forms/{form_id}/answers").json()["counts"]


def form_status(client: TestClient) -> str:
    return seeded_forms(client)[1]["status"]


def test_open_counts_unsettled_doubts_and_empty_fields(client: TestClient) -> None:
    form_id = annex_7(client)
    ai_answers(client, form_id, ANNEX_7_DOUBTS)

    # 9 fillable fields: all open but the automatic one (3 doubts, 1 missing, 4 never answered).
    assert counts(client, form_id)["open"] == 8


def test_keeping_a_doubt_or_leaving_a_field_empty_settles_it(client: TestClient) -> None:
    form_id = annex_7(client)
    ids = ai_answers(client, form_id, ANNEX_7_DOUBTS)
    before = counts(client, form_id)

    client.patch(
        f"/forms/{form_id}/fields/{ids['name_and_legal_form']}", json={"value": "Alpenlogic AG"}
    )
    kept = counts(client, form_id)
    client.patch(
        f"/forms/{form_id}/fields/{ids['first_name_s_and_surname_s']}", json={"value": None}
    )
    left_empty = counts(client, form_id)

    assert (kept["open"], kept["doubts"]) == (before["open"] - 1, before["doubts"] - 1)
    assert (left_empty["open"], left_empty["empty"]) == (kept["open"] - 1, kept["empty"])


def test_the_form_is_ready_once_nothing_is_open_and_not_started_after_discard(
    client: TestClient,
) -> None:
    form_id = annex_7(client)
    fields = [f for f in client.get(f"/forms/{form_id}").json()["fields"] if f["kind"] == "text"]

    for field in fields[:-1]:
        client.patch(f"/forms/{form_id}/fields/{field['id']}", json={"value": "x"})
    assert form_status(client) == "in_review"
    client.patch(f"/forms/{form_id}/fields/{fields[-1]['id']}", json={"value": None})
    assert (form_status(client), counts(client, form_id)["open"]) == ("ready", 0)

    client.delete(f"/forms/{form_id}/fill")
    assert (form_status(client), counts(client, form_id)["open"]) == ("not_started", 9)


def test_a_finished_fill_with_nothing_to_review_is_ready(client: TestClient) -> None:
    form_id = annex_7(client)
    fields = [f for f in client.get(f"/forms/{form_id}").json()["fields"] if f["kind"] == "text"]

    ai_answers(client, form_id, {f["key"]: (AnswerType.AUTO, "x") for f in fields})

    assert form_status(client) == "ready"


def test_clearing_an_automatic_value_by_hand_keeps_the_form_ready(
    client: TestClient,
) -> None:
    form_id = annex_7(client)
    fields = [f for f in client.get(f"/forms/{form_id}").json()["fields"] if f["kind"] == "text"]
    ai_answers(client, form_id, {f["key"]: (AnswerType.AUTO, "x") for f in fields})

    # Clearing an automatic value by hand leaves the field empty on purpose: still ready.
    client.patch(f"/forms/{form_id}/fields/{fields[0]['id']}", json={"value": None})

    assert form_status(client) == "ready"
