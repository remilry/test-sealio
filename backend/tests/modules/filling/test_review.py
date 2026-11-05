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
