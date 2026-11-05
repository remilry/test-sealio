"""Retry: only the fields a fill could not answer are filled again; the rest stays as it is."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.llm.facade import LLMRequest, LLMResult, OnPartial
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling import router as filling_router
from tests.modules.filling.test_ai_fill import ANNEX_7_ANSWER, ANNEX_7_KEY, read_events
from tests.modules.filling.test_parallel_fill import annex_4_keys
from tests.modules.helpers import add_demo_documents, fields_by_key, seeded_forms


class FlakyLLM(FakeLLM):
    """The recorded answers (plus Annex 7's scripted one), with simulated failures to set per
    test; `hook` runs inside each call (the user acting meanwhile)."""

    def __init__(self) -> None:
        answers = FakeLLM.from_dir(get_settings().llm_recordings_dir)._answers
        super().__init__({**answers, ANNEX_7_KEY: ANNEX_7_ANSWER})
        self.hook: Any = None

    def fail(self, prefix: str, times: int) -> None:
        self._failures[prefix] = times

    def generate_structured(  # type: ignore[override]
        self, request: LLMRequest[Any], on_partial: OnPartial | None = None
    ) -> LLMResult[Any]:
        if self.hook is not None:
            self.hook()
        return super().generate_structured(request, on_partial)


@pytest.fixture
def llm() -> Iterator[FlakyLLM]:
    fake = FlakyLLM()
    app.dependency_overrides[filling_router.get_language_model] = lambda: fake
    yield fake
    app.dependency_overrides.pop(filling_router.get_language_model, None)


@pytest.fixture
def client(llm: FlakyLLM) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client


def answers(client: TestClient, form_id: int) -> dict[int, dict[str, Any]]:
    state = client.get(f"/forms/{form_id}/answers").json()
    return {a["field_id"]: a for a in state["answers"]}


def partly_filled_annex_4(
    client: TestClient, llm: FlakyLLM, group: int = 0
) -> tuple[int, list[int]]:
    """Annex 4 filled with one group failing (both runs): its id and the failed fields."""
    annex_4 = seeded_forms(client)[0]["id"]
    llm.fail(annex_4_keys(client, annex_4)[group], 2)
    client.post(f"/forms/{annex_4}/fill")
    failed = client.get(f"/forms/{annex_4}/answers").json()["ai_run"]["failed_field_ids"]
    assert failed
    return annex_4, failed


def test_retry_answers_only_the_failed_fields(client: TestClient, llm: FlakyLLM) -> None:
    annex_4, failed = partly_filled_annex_4(client, llm)
    before = answers(client, annex_4)

    response = client.post(f"/forms/{annex_4}/fill/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "running"
    after = answers(client, annex_4)
    assert set(failed) <= after.keys()
    # Every answer already there is untouched.
    assert {k: after[k] for k in before} == before
    searching = [
        e["data"]["field_id"]
        for e in read_events(client, annex_4)
        if e["event"] == "field" and e["data"]["state"] == "searching"
    ]
    assert sorted(searching) == sorted(failed)
    run = client.get(f"/forms/{annex_4}/answers").json()["ai_run"]
    assert (run["status"], run["failed_field_ids"], run["error"]) == ("done", [], None)


def test_retry_skips_fields_the_user_filled(client: TestClient, llm: FlakyLLM) -> None:
    # Table 2: several fields, one the user fills.
    annex_4, failed = partly_filled_annex_4(client, llm, group=1)
    assert len(failed) > 1
    keys = {f["id"]: key for key, f in fields_by_key(client, annex_4).items()}
    client.patch(f"/forms/{annex_4}/fields/{failed[0]}", json={"value": "Typed by me"})
    llm.requests.clear()

    client.post(f"/forms/{annex_4}/fill/retry")

    assert answers(client, annex_4)[failed[0]]["value"] == "Typed by me"
    assert all(f"key: {keys[failed[0]]} " not in r.prompt for r in llm.requests)
    assert client.get(f"/forms/{annex_4}/answers").json()["ai_run"]["failed_field_ids"] == []


def test_retry_can_fail_again(client: TestClient, llm: FlakyLLM) -> None:
    annex_4, failed = partly_filled_annex_4(client, llm)
    llm.fail(annex_4_keys(client, annex_4)[0], 2)

    client.post(f"/forms/{annex_4}/fill/retry")

    run = client.get(f"/forms/{annex_4}/answers").json()["ai_run"]
    assert sorted(run["failed_field_ids"]) == sorted(failed)
    # Nothing could be answered this time.
    assert run["status"] == "failed"
    assert run["error"] is not None


def test_retry_after_a_fill_the_model_could_not_answer_at_all(
    client: TestClient, llm: FlakyLLM
) -> None:
    annex_7 = seeded_forms(client)[1]["id"]
    llm.fail(ANNEX_7_KEY, 2)
    client.post(f"/forms/{annex_7}/fill")
    assert client.get(f"/forms/{annex_7}/answers").json()["ai_run"]["status"] == "failed"

    client.post(f"/forms/{annex_7}/fill/retry")

    state = client.get(f"/forms/{annex_7}/answers").json()
    assert state["ai_run"]["status"] == "done"
    assert state["counts"]["filled"] > 0


def test_retry_refused_while_running(client: TestClient, llm: FlakyLLM) -> None:
    annex_4, _ = partly_filled_annex_4(client, llm)
    responses: list[Any] = []
    llm.hook = lambda: responses.append(client.post(f"/forms/{annex_4}/fill/retry"))

    client.post(f"/forms/{annex_4}/fill/retry")

    assert responses[0].status_code == 409
    assert responses[0].json()["detail"] == "This form is already being filled."


def test_retry_refused_when_nothing_failed(client: TestClient) -> None:
    annex_7 = seeded_forms(client)[1]["id"]
    client.post(f"/forms/{annex_7}/fill")

    response = client.post(f"/forms/{annex_7}/fill/retry")

    assert response.status_code == 409
    assert response.json()["detail"] == "Nothing to retry: every field has an answer."


def test_retry_of_an_unknown_form_is_404(client: TestClient) -> None:
    assert client.post("/forms/999999/fill/retry").status_code == 404


def test_discard_during_a_retry_stops_it(client: TestClient, llm: FlakyLLM) -> None:
    annex_4, _ = partly_filled_annex_4(client, llm)
    llm.hook = lambda: client.delete(f"/forms/{annex_4}/fill")

    client.post(f"/forms/{annex_4}/fill/retry")

    state = client.get(f"/forms/{annex_4}/answers").json()
    assert state["answers"] == []
    assert state["ai_run"] is None
