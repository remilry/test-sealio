"""Discarding a fill: every answer, the run and its events are deleted; the form is not started."""

import logging
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.llm.facade import LLMRequest, LLMResult, OnPartial
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling import job, service
from app.modules.filling import router as filling_router
from app.modules.filling.models import FillEventType
from app.modules.tenants import service as tenants_service
from tests.modules.filling.test_ai_fill import ANNEX_7_ANSWER, ANNEX_7_KEY, read_events
from tests.modules.helpers import add_demo_documents, fields_by_key, seeded_forms
from tests.modules.test_tenancy import ActAs, act_as  # noqa: F401


class HookedLLM(FakeLLM):
    """FakeLLM running `hook` inside the stream, once the first answer has been emitted."""

    def __init__(self) -> None:
        super().__init__({ANNEX_7_KEY: ANNEX_7_ANSWER})
        self.form_id = 0
        self.hook: Callable[[], None] | None = None
        self._fired = False

    def generate_structured(  # type: ignore[override]
        self, request: LLMRequest[Any], on_partial: OnPartial | None = None
    ) -> LLMResult[Any]:
        def both(partial: dict[str, Any]) -> None:
            if on_partial:
                on_partial(partial)
            if self.hook and not self._fired and _answered_events(self.form_id) >= 1:
                self._fired = True
                self.hook()

        return super().generate_structured(request, both)


def _tenant_fill_id(form_id: int) -> int | None:
    with SessionLocal() as session:
        return service.fill_id_of(session, tenants_service.get_current_tenant_id(session), form_id)


def _answered_events(form_id: int) -> int:
    with SessionLocal() as other:
        fill_id = service.fill_id_of(other, tenants_service.get_current_tenant_id(other), 2)
        return 0 if fill_id is None else _count(other, fill_id)


def _count(session: Any, fill_id: int) -> int:
    _, events = service.events_after(session, fill_id, 0)
    return sum(1 for e in events if e.type == FillEventType.FIELD and e.data["state"] == "answered")


@pytest.fixture
def llm() -> Iterator[HookedLLM]:
    fake = HookedLLM()
    app.dependency_overrides[filling_router.get_language_model] = lambda: fake
    yield fake
    app.dependency_overrides.pop(filling_router.get_language_model, None)


@pytest.fixture
def client(llm: HookedLLM) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client


@pytest.fixture
def annex_7(client: TestClient, llm: HookedLLM) -> int:
    llm.form_id = seeded_forms(client)[1]["id"]
    return llm.form_id


def _discard(form_id: int) -> None:
    with SessionLocal() as session:
        service.discard_fill(session, tenants_service.get_current_tenant_id(session), form_id)


def _start(form_id: int) -> int:
    with SessionLocal() as session:
        return service.start_ai_fill(
            session, tenants_service.get_current_tenant_id(session), form_id
        )


def test_discard_deletes_every_answer_the_users_included(client: TestClient, annex_7: int) -> None:
    telephone = fields_by_key(client, annex_7)["telephone"]
    client.patch(f"/forms/{annex_7}/fields/{telephone['id']}", json={"value": "044"})
    client.post(f"/forms/{annex_7}/fill")
    assert len(client.get(f"/forms/{annex_7}/answers").json()["answers"]) > 1

    assert client.delete(f"/forms/{annex_7}/fill").status_code == 204

    state = client.get(f"/forms/{annex_7}/answers").json()
    assert state["answers"] == []
    assert state["ai_run"] is None
    assert seeded_forms(client)[1]["status"] == "not_started"


def test_discard_of_a_form_never_started_is_204(client: TestClient, annex_7: int) -> None:
    assert client.delete(f"/forms/{annex_7}/fill").status_code == 204


def test_a_discarded_form_can_be_auto_filled_again(client: TestClient, annex_7: int) -> None:
    client.post(f"/forms/{annex_7}/fill")
    client.delete(f"/forms/{annex_7}/fill")

    assert client.post(f"/forms/{annex_7}/fill").status_code == 202


def test_discard_of_an_unknown_form_is_404(client: TestClient) -> None:
    assert client.delete("/forms/999999/fill").status_code == 404


def test_discard_of_another_tenants_fill_leaves_it(
    client: TestClient,
    annex_7: int,
    act_as: ActAs,  # noqa: F811
) -> None:
    telephone = fields_by_key(client, annex_7)["telephone"]
    client.patch(f"/forms/{annex_7}/fields/{telephone['id']}", json={"value": "044"})

    with act_as("helvetia-it"):
        assert client.delete(f"/forms/{annex_7}/fill").status_code == 204

    assert len(client.get(f"/forms/{annex_7}/answers").json()["answers"]) == 1


def test_discard_during_a_run_stops_the_job_silently(
    client: TestClient, annex_7: int, llm: HookedLLM, caplog: pytest.LogCaptureFixture
) -> None:
    fill_id = _start(annex_7)
    llm.hook = lambda: _discard(annex_7)

    with caplog.at_level(logging.DEBUG):
        job.run_fill(fill_id, llm)

    assert _tenant_fill_id(annex_7) is None
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert client.get(f"/forms/{annex_7}/answers").json()["ai_run"] is None


def test_discard_then_restart_during_the_old_run_never_writes_into_the_new_fill(
    client: TestClient, annex_7: int, llm: HookedLLM
) -> None:
    old_id = _start(annex_7)
    new_ids: list[int] = []

    def discard_and_restart() -> None:
        _discard(annex_7)
        new_ids.append(_start(annex_7))

    llm.hook = discard_and_restart

    job.run_fill(old_id, llm)

    [new_id] = new_ids
    assert new_id != old_id
    assert _tenant_fill_id(annex_7) == new_id
    with SessionLocal() as session:
        _, events = service.events_after(session, new_id, 0)
    assert events == []
    assert client.get(f"/forms/{annex_7}/answers").json()["answers"] == []


def test_the_event_stream_of_a_discarded_run_ends(client: TestClient, annex_7: int) -> None:
    client.post(f"/forms/{annex_7}/fill")
    client.delete(f"/forms/{annex_7}/fill")

    assert read_events(client, annex_7) == []
