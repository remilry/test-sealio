"""The fake model replays recorded answers by request key; the recorder writes them."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from app.llm.facade import LLMError, LLMRequest, LLMResult, LLMUsage, OnPartial
from app.llm.fake_adapter import FakeLLM, RecordingLLM


class Answer(BaseModel):
    value: str


def request(key: str) -> LLMRequest[Answer]:
    return LLMRequest(key=key, instructions="Be exact.", prompt="Which value?", schema=Answer)


def test_a_recorded_answer_is_replayed_as_the_requested_model(tmp_path: Path) -> None:
    (tmp_path / "annex--page-1.json").write_text(json.dumps({"value": "Alpenlogic AG"}))

    result = FakeLLM.from_dir(tmp_path).generate_structured(request("annex--page-1"))

    assert result.output == Answer(value="Alpenlogic AG")
    # A replay costs nothing.
    assert (result.usage.calls, result.usage.cost_usd) == (1, 0.0)


def test_an_unrecorded_request_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(LLMError, match="No recorded answer for 'other'"):
        FakeLLM.from_dir(tmp_path).generate_structured(request("other"))


def test_the_recorder_saves_what_the_model_answered_for_replay(tmp_path: Path) -> None:
    model = FakeLLM({"k": {"value": "CHF 500,000"}})

    RecordingLLM(model, tmp_path / "recordings").generate_structured(request("k"))

    replayed = FakeLLM.from_dir(tmp_path / "recordings").generate_structured(request("k"))
    assert replayed.output == Answer(value="CHF 500,000")


class Fields(BaseModel):
    fields: list[dict[str, int]]


def fields_request() -> LLMRequest[Fields]:
    return LLMRequest(key="k", instructions="", prompt="", schema=Fields)


FIELDS_ANSWER = {"fields": [{"a": 1}, {"a": 2}, {"a": 3}]}


def test_replay_streams_partial_outputs_in_order() -> None:
    partials: list[dict[str, Any]] = []

    FakeLLM({"k": FIELDS_ANSWER}).generate_structured(fields_request(), partials.append)

    lengths = [len(p.get("fields", [])) for p in partials]
    assert partials
    assert lengths == sorted(lengths)
    assert partials[-1] == FIELDS_ANSWER


def test_replay_without_latency_never_sleeps() -> None:
    sleeps: list[float] = []

    FakeLLM({"k": FIELDS_ANSWER}, latency="none", sleep=sleeps.append).generate_structured(
        fields_request(), lambda _: None
    )

    assert sleeps == []


def test_replay_with_recorded_latency_spreads_the_recorded_time() -> None:
    sleeps: list[float] = []
    recording = {**FIELDS_ANSWER, "timing": {"first_output_seconds": 4.0, "total_seconds": 10.0}}

    FakeLLM({"k": recording}, latency="recorded", sleep=sleeps.append).generate_structured(
        fields_request(), lambda _: None
    )

    assert sleeps[0] == 4.0
    assert sum(sleeps) == pytest.approx(10.0)


def test_timing_is_not_part_of_the_output() -> None:
    class Strict(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: str

    recording = {"value": "x", "timing": {"first_output_seconds": 1.0, "total_seconds": 2.0}}

    result = FakeLLM({"k": recording}).generate_structured(
        LLMRequest(key="k", instructions="", prompt="", schema=Strict)
    )

    assert result.output == Strict(value="x")


def test_recording_writes_the_timing(tmp_path: Path) -> None:
    class Stub:
        def generate_structured[T: BaseModel](
            self, request: LLMRequest[T], on_partial: OnPartial | None = None
        ) -> LLMResult[T]:
            if on_partial:
                on_partial({"value": "CH"})
            return LLMResult(
                output=request.schema.model_validate({"value": "CHF"}), usage=LLMUsage(calls=1)
            )

    partials: list[dict[str, Any]] = []
    RecordingLLM(Stub(), tmp_path).generate_structured(request("k"), partials.append)

    timing = json.loads((tmp_path / "k.json").read_text())["timing"]
    assert timing["first_output_seconds"] <= timing["total_seconds"]
    assert partials == [{"value": "CH"}]
