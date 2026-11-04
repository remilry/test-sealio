"""The fake model replays recorded answers by request key; the recorder writes them."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.llm.facade import LLMError, LLMRequest
from app.llm.fake_adapter import FakeLLM, RecordingLLM


class Answer(BaseModel):
    value: str


def request(key: str) -> LLMRequest[Answer]:
    return LLMRequest(key=key, instructions="Be exact.", prompt="Which value?", schema=Answer)


def test_a_recorded_answer_is_replayed_as_the_requested_model(tmp_path: Path) -> None:
    (tmp_path / "annex--page-1.json").write_text(json.dumps({"value": "Alpenlogic AG"}))

    answer = FakeLLM.from_dir(tmp_path).generate_structured(request("annex--page-1"))

    assert answer == Answer(value="Alpenlogic AG")


def test_an_unrecorded_request_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(LLMError, match="No recorded answer for 'other'"):
        FakeLLM.from_dir(tmp_path).generate_structured(request("other"))


def test_the_recorder_saves_what_the_model_answered_for_replay(tmp_path: Path) -> None:
    model = FakeLLM({"k": {"value": "CHF 500,000"}})

    RecordingLLM(model, tmp_path / "recordings").generate_structured(request("k"))

    replayed = FakeLLM.from_dir(tmp_path / "recordings").generate_structured(request("k"))
    assert replayed == Answer(value="CHF 500,000")
