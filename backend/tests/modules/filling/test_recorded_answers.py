"""The real model's recorded answers for Annex 7 (llm_recordings/, scripts/record_llm.py), replayed
through the whole fill as in the e2e scenario and the dev mode: what the demo shows."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling import router as filling_router
from app.modules.filling.rules import NEEDS_REVIEW, AnswerType
from scripts.ground_truth import ANNEX_4, check
from tests.modules.helpers import add_demo_documents, fields_by_key, seeded_forms


@pytest.fixture
def client() -> Iterator[TestClient]:
    replay = FakeLLM.from_dir(get_settings().llm_recordings_dir)
    app.dependency_overrides[filling_router.get_language_model] = lambda: replay
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client
    app.dependency_overrides.pop(filling_router.get_language_model, None)


def test_the_recorded_annex_7_fill_matches_the_ground_truth(client: TestClient) -> None:
    annex_7 = seeded_forms(client)[1]["id"]
    keys = {f["id"]: key for key, f in fields_by_key(client, annex_7).items()}

    client.post(f"/forms/{annex_7}/fill")

    state = client.get(f"/forms/{annex_7}/answers").json()
    answers = {keys[a["field_id"]]: (a["type"], a["value"]) for a in state["answers"]}
    # knowledge-base/GROUND_TRUTH.md, Annex 7.
    assert answers == {
        "project_number_project_title_project_name": (
            "auto",
            "ZH-2026-0412 · Cloud Platform Services – Canton of Zurich",
        ),
        "name_of_the_contracting_authority": (
            "auto",
            "Canton of Zurich, Office for Information Technology",
        ),
        "name_and_legal_form": (
            "auto",
            "Alpenlogic AG, Company limited by shares (Aktiengesellschaft, AG)",
        ),
        "business_address": ("auto", "Pfingstweidstrasse 31, 8005 Zurich"),
        "contact_person": ("auto", "Marc Keller"),
        "telephone": ("auto", "+41 44 555 01 20"),
        "e_mail": ("auto", "marc.keller@alpenlogic.example"),
        "place_and_date": ("manual", "Zurich, 04.11.2026"),
        "first_name_s_and_surname_s": ("auto", "Marc Keller"),
    }
    assert state["ai_run"]["status"] == "done"


def _annex_4_answers(client: TestClient) -> dict[str, tuple[AnswerType, str | None]]:
    annex_4 = seeded_forms(client)[0]["id"]
    keys = {f["id"]: key for key, f in fields_by_key(client, annex_4).items()}
    state = client.get(f"/forms/{annex_4}/answers").json()
    assert state["ai_run"]["status"] == "done"
    return {keys[a["field_id"]]: (AnswerType(a["type"]), a["value"]) for a in state["answers"]}


def test_the_recorded_annex_4_fill_has_no_silent_error(client: TestClient) -> None:
    # knowledge-base/GROUND_TRUTH.md through scripts/ground_truth.py: every answer is as expected,
    # or shown to the user as to check (a doubt), never wrong without a flag.
    client.post(f"/forms/{seeded_forms(client)[0]['id']}/fill")

    answers = _annex_4_answers(client)

    problems = {key: p for key, p in check(ANNEX_4, answers).items() if p is not None}
    silent = {key: p for key, p in problems.items() if answers[key][0] not in NEEDS_REVIEW}
    assert silent == {}
    # Known doubts of this recording (docs/PLAN.md 6c, known limits): flagged, for the user.
    assert set(problems) == {
        "registered_office",  # the two runs worded it differently (city / address)
        "share_capital",  # one run added the superseded CHF 100,000
        "auxiliary_staff",  # one run read "5 other staff and apprentices"
        "have_you_paid_in_full_the_contributions_due_under_generally_",  # one run skipped it
        "have_any_seizures_been_carried_out_against_you_in_the_past_t",  # one run skipped it
    }
