"""The fill's model calls run in parallel, one per call group, each with its own database session.

On the seeded Annex 4 (9 groups), with a fake model that waits before answering like the real one.
"""

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.llm.facade import LLMError, LLMRequest, LLMResult, OnPartial
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling import job
from app.modules.filling import router as filling_router
from app.modules.filling.answer_engine import request_key
from app.modules.filling.groups import FieldToAnswer, call_groups
from app.modules.filling.llm_schema import LLMSectionAnswer
from app.modules.forms.parsing.schema import FieldKind
from tests.modules.filling.test_ai_fill import read_events
from tests.modules.helpers import add_demo_documents, fields_by_key, seeded_forms

ANNEX_4 = "Annex_4_Conditions of Participation and Company Self-Declaration.docx"
DELAY = 0.3


def annex_4_keys(client: TestClient, form_id: int) -> list[str]:
    fields = [
        FieldToAnswer(f["id"], key, f["label"], FieldKind(f["kind"]), section=f["section"])
        for key, f in fields_by_key(client, form_id).items()
        if f["kind"] != "signature"
    ]
    return [request_key(ANNEX_4, g.section, g.part) for g in call_groups(fields)]


class SlowLLM(FakeLLM):
    """Answers every group with nothing found after DELAY; `failing` keys raise at once;
    `while_calling` runs inside the first call, while the others are waiting."""

    def __init__(self) -> None:
        super().__init__({})
        self.failing: set[str] = set()
        self.while_calling: Any = None
        self._lock = threading.Lock()
        # (start, end) of each call, to see them overlap.
        self.spans: list[tuple[float, float]] = []

    def generate_structured(  # type: ignore[override]
        self, request: LLMRequest[Any], on_partial: OnPartial | None = None
    ) -> LLMResult[Any]:
        if request.key in self.failing:
            raise LLMError("rate limited")
        with self._lock:
            hook, self.while_calling = self.while_calling, None
        if hook is not None:
            hook()
        began = time.monotonic()
        time.sleep(DELAY)
        with self._lock:
            self.spans.append((began, time.monotonic()))
        self._answers[request.key] = {"fields": []}
        return super().generate_structured(request, on_partial)


@pytest.fixture
def llm() -> Iterator[SlowLLM]:
    fake = SlowLLM()
    app.dependency_overrides[filling_router.get_language_model] = lambda: fake
    yield fake
    app.dependency_overrides.pop(filling_router.get_language_model, None)


@pytest.fixture
def client(llm: SlowLLM) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        add_demo_documents()
        yield test_client


@pytest.fixture
def annex_4(client: TestClient) -> int:
    return seeded_forms(client)[0]["id"]


def test_annex_4_is_answered_by_nine_calls(client: TestClient, annex_4: int) -> None:
    keys = annex_4_keys(client, annex_4)

    assert len(keys) == 9
    assert (
        "annex-4-conditions-of-participation-and-company-self-declaration--table-7--part-2" in keys
    )


def test_groups_are_called_in_parallel(client: TestClient, annex_4: int, llm: SlowLLM) -> None:
    client.post(f"/forms/{annex_4}/fill")

    # Every call has started before the first one ends: they all run at the same time.
    assert len(llm.spans) == 9
    assert max(start for start, _ in llm.spans) < min(end for _, end in llm.spans)
    events = read_events(client, annex_4)
    answered = [e for e in events if e["event"] == "field" and e["data"]["state"] == "answered"]
    assert len(answered) == 48
    assert [e["event"] for e in events].count("done") == 1
    state = client.get(f"/forms/{annex_4}/answers").json()
    assert state["ai_run"]["status"] == "done"
    assert answered[-1]["data"]["counts"] == state["counts"]


def test_every_field_is_searching_before_any_answer(client: TestClient, annex_4: int) -> None:
    client.post(f"/forms/{annex_4}/fill")

    states = [e["data"]["state"] for e in read_events(client, annex_4) if e["event"] == "field"]
    assert states == ["searching"] * 48 + ["answered"] * 48


def test_a_failing_group_ends_the_run_and_the_others_stop_publishing(
    client: TestClient, annex_4: int, llm: SlowLLM
) -> None:
    llm.failing = {annex_4_keys(client, annex_4)[0]}

    client.post(f"/forms/{annex_4}/fill")

    events = read_events(client, annex_4)
    kinds = [e["event"] for e in events]
    assert kinds[-1] == "error"
    assert "done" not in kinds
    assert events[-1]["data"]["message"] == job.MODEL_ERROR
    assert not any(e["event"] == "field" and e["data"]["state"] == "answered" for e in events)
    assert client.get(f"/forms/{annex_4}/answers").json()["ai_run"]["status"] == "failed"


def test_discard_while_groups_are_calling_writes_nothing(
    client: TestClient, annex_4: int, llm: SlowLLM
) -> None:
    llm.while_calling = lambda: client.delete(f"/forms/{annex_4}/fill")

    client.post(f"/forms/{annex_4}/fill")

    state = client.get(f"/forms/{annex_4}/answers").json()
    assert state["answers"] == []
    assert state["ai_run"] is None
    assert seeded_forms(client)[0]["status"] == "not_started"


def test_the_same_model_replays_concurrent_fills_identically(client: TestClient) -> None:
    replay = FakeLLM({"a": {"fields": [], "timing": {"x": 1}}})
    request = LLMRequest(key="a", instructions="", prompt="", schema=LLMSectionAnswer)

    results = run_twice(lambda: replay.generate_structured(request))

    assert results[0] == results[1]
    assert replay._answers["a"]["timing"] == {"x": 1}  # pyright: ignore[reportPrivateUsage]


def run_twice(call: Any) -> list[Any]:
    out: list[Any] = [None, None]

    def worker(i: int) -> None:
        out[i] = call().output

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def test_twelve_groups_on_ten_workers_finish() -> None:
    def work(i: int) -> int:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            time.sleep(0.2)
        return i

    started = time.monotonic()
    results = job.run_groups(list(range(12)), work, max_workers=10, stop=threading.Event())

    assert results == list(range(12))
    assert time.monotonic() - started < 5


def test_run_groups_stops_the_others_on_the_first_error() -> None:
    ran: list[int] = []
    stop = threading.Event()

    def work(i: int) -> int:
        if i == 0:
            raise ValueError("boom")
        time.sleep(0.1)
        ran.append(i)
        return i

    with pytest.raises(ValueError, match="boom"):
        job.run_groups(list(range(6)), work, max_workers=1, stop=stop)

    assert stop.is_set()
    assert ran == []
