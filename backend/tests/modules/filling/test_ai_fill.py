"""AI fill of Annex 7 end to end through the API, with a scripted model (no key, no network)."""

import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.llm.facade import LLMError, LLMRequest, LLMResult, OnPartial
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling import router as filling_router
from app.modules.filling import service
from app.modules.filling.answer_engine import request_key
from app.modules.filling.models import AiStatus, FillEventType
from app.modules.tenants import service as tenants_service
from tests.modules.helpers import add_demo_documents, fields_by_key, seeded_forms

ANNEX_7_KEY = request_key("Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf", "Page 1")


def field(key: str, *candidates: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "field": key,
        "user_only": False,
        "user_only_reason": None,
        "suggested_value": None,
        "candidates": list(candidates),
    } | extra


def candidate(value: str, *quotes: str, passage: str = "P1") -> dict[str, Any]:
    return {
        "value": value,
        "citations": [{"passage": passage, "quote": quote} for quote in quotes],
        "source_date": None,
        "valid_until": None,
    }


# What the model answers for Annex 7, quoting the demo documents and the tender details. The
# passage labels are deliberately wrong: the validator finds the passage holding each quote.
ANNEX_7_ANSWER = {
    "fields": [
        field(
            "project_number_project_title_project_name",
            candidate(
                "ZH-2026-0412 / Cloud Platform Services – Canton of Zurich",
                "Project number (reference): ZH-2026-0412",
                "Project title: Cloud Platform Services – Canton of Zurich",
            ),
        ),
        field(
            "name_of_the_contracting_authority",
            candidate(
                "Canton of Zurich, Office for Information Technology",
                "Contracting authority: Canton of Zurich, Office for Information Technology",
            ),
        ),
        field(
            "name_and_legal_form",
            candidate(
                "Alpenlogic AG, company limited by shares (AG)",
                "Alpenlogic AG",
                "Company limited by shares (Aktiengesellschaft, AG)",
            ),
        ),
        field(
            "business_address",
            candidate("Pfingstweidstrasse 31, 8005 Zurich", "Pfingstweidstrasse 31, 8005 Zurich"),
        ),
        field("contact_person", candidate("Marc Keller", "Keller, Marc")),
        # Nothing found: left empty.
        field("telephone"),
        # Invented: its quote is in no passage, so it is rejected.
        field("e_mail", candidate("tenders@alpenlogic.example", "tenders@alpenlogic.example")),
        field(
            "place_and_date",
            user_only=True,
            user_only_reason="Place and date of signing are yours to set.",
            suggested_value="Zurich, 4 November 2026",
        ),
        field("first_name_s_and_surname_s", candidate("Marc Keller", "Keller, Marc")),
    ]
}


class ScriptedLLM(FakeLLM):
    """FakeLLM that can run code while "thinking" (e.g. the user saving a field meanwhile)."""

    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        super().__init__(answers)
        self.while_thinking: Callable[[], None] | None = None

    def generate_structured(  # type: ignore[override]
        self, request: LLMRequest[Any], on_partial: OnPartial | None = None
    ) -> LLMResult[Any]:
        if self.while_thinking:
            self.while_thinking()
        return super().generate_structured(request, on_partial)


@pytest.fixture
def llm() -> Iterator[ScriptedLLM]:
    fake = ScriptedLLM({ANNEX_7_KEY: ANNEX_7_ANSWER})
    app.dependency_overrides[filling_router.get_language_model] = lambda: fake
    yield fake
    app.dependency_overrides.pop(filling_router.get_language_model, None)


@pytest.fixture
def client(llm: ScriptedLLM) -> Iterator[TestClient]:
    """The app with the demo company's documents added (they are not seeded)."""
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client


@pytest.fixture
def annex_7(client: TestClient) -> int:
    return seeded_forms(client)[1]["id"]


def answers_by_key(client: TestClient, form_id: int) -> dict[str, dict[str, Any]]:
    ids = {f["id"]: key for key, f in fields_by_key(client, form_id).items()}
    state = client.get(f"/forms/{form_id}/answers").json()
    return {ids[a["field_id"]]: a for a in state["answers"]}


def read_events(client: TestClient, form_id: int, last_event_id: int | None = None) -> list[dict]:
    headers = {} if last_event_id is None else {"Last-Event-ID": str(last_event_id)}
    response = client.get(f"/forms/{form_id}/fill/events", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            events.append(
                {"id": int(lines["id"]), "event": lines["event"], "data": json.loads(lines["data"])}
            )
    return events


def test_starting_the_ai_fill_answers_in_the_background(client: TestClient, annex_7: int) -> None:
    response = client.post(f"/forms/{annex_7}/fill")

    assert response.status_code == 202
    assert response.json()["status"] == "running"
    # The background task has run once the response is read (TestClient).
    state = client.get(f"/forms/{annex_7}/answers").json()
    assert state["ai_run"]["status"] == "done"
    assert state["ai_run"]["finished_at"] is not None
    assert seeded_forms(client)[1]["status"] == "in_review"


def test_a_verified_answer_is_filled_automatically_with_its_source(
    client: TestClient, annex_7: int
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    answer = answers_by_key(client, annex_7)["name_and_legal_form"]

    assert answer["value"] == "Alpenlogic AG, company limited by shares (AG)"
    assert (answer["type"], answer["resolved_by"], answer["needs_review"]) == ("auto", "ai", False)
    [chosen] = answer["candidates"]
    sources = {(c["document_name"], c["page"]) for c in chosen["citations"]}
    assert ("Commercial register extract", 0) in sources
    assert all(c["chunk_id"] and c["document_id"] for c in chosen["citations"])


def test_the_tender_details_are_a_source(client: TestClient, annex_7: int) -> None:
    client.post(f"/forms/{annex_7}/fill")

    answers = answers_by_key(client, annex_7)

    authority = answers["name_of_the_contracting_authority"]
    assert authority["value"] == "Canton of Zurich, Office for Information Technology"
    [citation] = authority["candidates"][0]["citations"]
    assert (citation["document_name"], citation["document_id"]) == ("Tender details", None)
    assert answers["project_number_project_title_project_name"]["type"] == "auto"


def test_nothing_found_or_an_unverified_answer_leaves_the_field_empty(
    client: TestClient, annex_7: int
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    answers = answers_by_key(client, annex_7)

    for key in ("telephone", "e_mail"):
        assert answers[key]["value"] is None
        assert (answers[key]["type"], answers[key]["needs_review"]) == ("missing", True)
        assert answers[key]["candidates"] == []


def test_a_user_only_field_is_pre_written_and_left_to_review(
    client: TestClient, annex_7: int
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    place = answers_by_key(client, annex_7)["place_and_date"]

    assert place["value"] == "Zurich, 4 November 2026"
    assert (place["type"], place["needs_review"]) == ("manual", True)
    assert place["user_only_reason"] == "Place and date of signing are yours to set."


def test_the_signature_is_never_sent_to_the_model_nor_filled(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    assert "signature_s" not in answers_by_key(client, annex_7)
    [request] = llm.requests
    assert "signature_s" not in request.prompt
    state = client.get(f"/forms/{annex_7}/answers").json()
    # 9 fillable: 7 with a value (6 sourced + the pre-written place and date).
    assert state["counts"] == {"fillable": 9, "filled": 7, "empty": 2, "doubts": 0}


def test_one_model_call_per_section_with_the_tender_and_the_passages(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    [request] = llm.requests
    assert request.key == "annex-7-self-declaration-art29c-ukraine-ordinance--page-1"
    assert "Alpenlogic AG" in request.instructions
    assert "[P1] Tender details\nProject title: Cloud Platform Services" in request.prompt
    assert "Commercial register extract, page 1" in request.prompt
    assert "key: e_mail · label: E-mail · kind: text" in request.prompt


def test_the_events_replay_the_five_phases_and_each_answer(
    client: TestClient, annex_7: int
) -> None:
    client.post(f"/forms/{annex_7}/fill")

    events = read_events(client, annex_7)

    phases = [e["data"]["phase"] for e in events if e["event"] == "phase"]
    assert phases == [
        "reading_form",
        "detecting_fields",
        "searching",
        "cross_checking",
        "preparing_review",
    ]
    detected = next(e["data"] for e in events if e["event"] == "phase")
    assert detected == {"phase": "reading_form", "file_format": "pdf", "pages": 1, "sections": 1}
    fields = [e["data"] for e in events if e["event"] == "field"]
    assert [f["state"] for f in fields] == ["searching"] * 9 + ["answered"] * 9
    assert fields[-1]["counts"]["filled"] == 7
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["filled"] == 7
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)


def test_the_events_resume_after_the_last_event_received(client: TestClient, annex_7: int) -> None:
    client.post(f"/forms/{annex_7}/fill")
    events = read_events(client, annex_7)

    resumed = read_events(client, annex_7, last_event_id=events[10]["id"])

    assert resumed == events[11:]


def test_no_events_when_the_ai_never_ran(client: TestClient, annex_7: int) -> None:
    assert read_events(client, annex_7) == []
    assert client.get("/forms/999999/fill/events").status_code == 404


def test_a_value_the_user_saved_is_kept_when_the_ai_fills_again(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    contact = fields_by_key(client, annex_7)["contact_person"]
    client.patch(f"/forms/{annex_7}/fields/{contact['id']}", json={"value": "Sofia Brunner"})

    client.post(f"/forms/{annex_7}/fill")

    answer = answers_by_key(client, annex_7)["contact_person"]
    assert (answer["value"], answer["resolved_by"]) == ("Sofia Brunner", "user")
    # Not even asked again.
    assert "contact_person" not in llm.requests[0].prompt


def test_a_value_the_user_saves_while_the_ai_is_filling_wins(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    address = fields_by_key(client, annex_7)["business_address"]

    def user_saves() -> None:
        with SessionLocal() as session:
            tenant_id = tenants_service.get_current_tenant_id(session)
            service.set_answer(session, tenant_id, annex_7, address["id"], "Hardstrasse 201")

    llm.while_thinking = user_saves
    client.post(f"/forms/{annex_7}/fill")

    answer = answers_by_key(client, annex_7)["business_address"]
    assert (answer["value"], answer["resolved_by"]) == ("Hardstrasse 201", "user")


def test_the_fill_cannot_start_twice_at_once(client: TestClient, annex_7: int) -> None:
    with SessionLocal() as session:
        service.start_ai_fill(session, tenants_service.get_current_tenant_id(session), annex_7)

    response = client.post(f"/forms/{annex_7}/fill")

    assert response.status_code == 409
    assert "already being filled" in response.json()["detail"]


def test_a_form_that_cannot_be_read_yet_cannot_be_filled(client: TestClient) -> None:
    annex_4 = seeded_forms(client)[0]["id"]

    response = client.post(f"/forms/{annex_4}/fill")

    assert response.status_code == 422


def test_a_model_failure_ends_the_fill_with_a_message(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    def fail() -> None:
        raise LLMError("The language model failed: timeout")

    llm.while_thinking = fail
    client.post(f"/forms/{annex_7}/fill")

    state = client.get(f"/forms/{annex_7}/answers").json()
    assert state["ai_run"]["status"] == "failed"
    last = read_events(client, annex_7)[-1]
    assert last == {
        "id": last["id"],
        "event": "error",
        "data": {"message": "The language model failed: timeout"},
    }


def test_an_unexpected_failure_shows_a_generic_message(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    def crash() -> None:
        raise RuntimeError("bug")

    llm.while_thinking = crash
    client.post(f"/forms/{annex_7}/fill")

    assert read_events(client, annex_7)[-1]["data"] == {
        "message": "Something went wrong while filling this form."
    }


def test_a_fill_interrupted_by_a_server_stop_ends_as_failed(
    client: TestClient, annex_7: int
) -> None:
    with SessionLocal() as session:
        service.start_ai_fill(session, tenants_service.get_current_tenant_id(session), annex_7)
        service.fail_interrupted_fills(session)

    assert client.get(f"/forms/{annex_7}/answers").json()["ai_run"]["status"] == "failed"
    assert "server stopped" in read_events(client, annex_7)[-1]["data"]["message"]


def test_without_an_api_key_the_fill_is_refused_clearly(
    client: TestClient, annex_7: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_key() -> None:
        raise LLMError("OPENAI_API_KEY is not set (backend/.env).")

    app.dependency_overrides.pop(filling_router.get_language_model)
    monkeypatch.setattr(filling_router, "get_llm", no_key)

    response = client.post(f"/forms/{annex_7}/fill")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
    assert not re.search(r"\bAI\b", response.json()["detail"])
    assert client.get(f"/forms/{annex_7}/answers").json()["ai_run"] is None


def test_the_events_of_a_running_fill_arrive_live_until_it_ends(
    client: TestClient, annex_7: int
) -> None:
    with SessionLocal() as session:
        fill_id = service.start_ai_fill(
            session, tenants_service.get_current_tenant_id(session), annex_7
        )

    def ai_working() -> None:
        with SessionLocal() as session:
            for phase in ("reading_form", "detecting_fields"):
                time.sleep(0.3)
                service.add_event(session, fill_id, FillEventType.PHASE, {"phase": phase})
            time.sleep(0.3)
            service.finish_ai_fill(session, fill_id, AiStatus.DONE)
            service.add_event(session, fill_id, FillEventType.DONE, {"filled": 0})

    worker = threading.Thread(target=ai_working)
    worker.start()
    events = read_events(client, annex_7)
    worker.join()

    assert [e["event"] for e in events] == ["phase", "phase", "done"]


def test_the_cost_and_timing_of_the_fill_are_logged(
    client: TestClient, annex_7: int, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.modules.filling.job"):
        client.post(f"/forms/{annex_7}/fill")

    messages = [r.getMessage() for r in caplog.records]
    [section] = [m for m in messages if "section 'Page 1'" in m]
    assert "search " in section
    assert "passages) · model 1 call(s)" in section
    [done] = [m for m in messages if " done in " in m]
    assert "7/9 filled" in done
    assert "$0.0000" in done


def test_an_answer_naming_the_field_by_its_label_is_still_matched(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    by_label = {"fields": [field("Business address", *ANNEX_7_ANSWER["fields"][3]["candidates"])]}
    llm._answers[ANNEX_7_KEY] = by_label

    client.post(f"/forms/{annex_7}/fill")

    assert answers_by_key(client, annex_7)["business_address"]["type"] == "auto"


def test_answers_are_emitted_while_the_section_is_being_answered(
    client: TestClient, annex_7: int, llm: ScriptedLLM
) -> None:
    answered_during_call: list[int] = []

    def answered_events() -> int:
        with SessionLocal() as other:
            fill_id = service.fill_id_of(
                other, tenants_service.get_current_tenant_id(other), annex_7
            )
            if fill_id is None:
                return 0
            _, events = service.events_after(other, fill_id, 0)
            return sum(
                1 for e in events if e.type == FillEventType.FIELD and e.data["state"] == "answered"
            )

    def watch(partial: dict[str, Any]) -> None:
        answered_during_call.append(answered_events())

    class Watching(ScriptedLLM):
        def generate_structured(  # type: ignore[override]
            self, request: LLMRequest[Any], on_partial: OnPartial | None = None
        ) -> LLMResult[Any]:
            def both(partial: dict[str, Any]) -> None:
                if on_partial:
                    on_partial(partial)
                watch(partial)

            return super().generate_structured(request, both)

    app.dependency_overrides[filling_router.get_language_model] = lambda: Watching(
        {ANNEX_7_KEY: ANNEX_7_ANSWER}
    )

    client.post(f"/forms/{annex_7}/fill")

    # Some answers were already recorded before the model's call returned.
    assert max(answered_during_call) >= 1
