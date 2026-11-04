"""Deterministic stand-ins for the real model: no key, no network.

`FakeLLM` replays answers by request key: recorded from the real model (`RecordingLLM`, see
scripts/record_llm.py) into `<key>.json` files, or given directly by a test. A replay streams the
answer in chunks like the real model does; a recording may carry a `timing` key, which `FakeLLM`
replays when `latency="recorded"`.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_core import from_json

from app.llm.facade import LLM, LLMError, LLMRequest, LLMResult, LLMUsage, OnPartial

CHUNKS = 20


class FakeLLM:
    def __init__(
        self,
        answers: dict[str, dict[str, Any]],
        *,
        latency: Literal["recorded", "none"] = "none",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._answers = answers
        self._latency = latency
        self._sleep = sleep
        # Every request received, for tests to look at the prompts.
        self.requests: list[LLMRequest[Any]] = []

    @classmethod
    def from_dir(cls, directory: Path, *, latency: Literal["recorded", "none"] = "none") -> FakeLLM:
        answers = {path.stem: json.loads(path.read_text()) for path in directory.glob("*.json")}
        return cls(answers, latency=latency)

    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        self.requests.append(request)
        recording = self._answers.get(request.key)
        if recording is None:
            raise LLMError(f"No recorded answer for {request.key!r} (scripts/record_llm.py).")
        answer = dict(recording)
        timing = answer.pop("timing", None)
        if on_partial is not None:
            self._stream(answer, timing, on_partial)
        # A replay costs nothing.
        return LLMResult(output=request.schema.model_validate(answer), usage=LLMUsage(calls=1))

    def _stream(
        self, answer: dict[str, Any], timing: dict[str, float] | None, on_partial: OnPartial
    ) -> None:
        text = json.dumps(answer, ensure_ascii=False)
        size = -(-len(text) // CHUNKS)
        first, total = (0.0, 0.0)
        if self._latency == "recorded" and timing:
            first, total = timing["first_output_seconds"], timing["total_seconds"]
        for index in range(CHUNKS):
            delay = first if index == 0 else (total - first) / (CHUNKS - 1)
            if delay > 0:
                self._sleep(delay)
            partial = from_json(text[: size * (index + 1)], allow_partial=True)
            if isinstance(partial, dict):
                on_partial(partial)


class RecordingLLM:
    """Calls a real model and writes each answer to `<directory>/<key>.json` for FakeLLM."""

    def __init__(self, llm: LLM, directory: Path) -> None:
        self._llm = llm
        self._directory = directory

    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        started = time.monotonic()
        first_output: list[float] = []

        def watch(partial: dict[str, Any]) -> None:
            if not first_output:
                first_output.append(time.monotonic() - started)
            if on_partial is not None:
                on_partial(partial)

        result = self._llm.generate_structured(request, watch)
        total = time.monotonic() - started
        recording = {
            **result.output.model_dump(mode="json"),
            "timing": {
                "first_output_seconds": round(first_output[0] if first_output else total, 2),
                "total_seconds": round(total, 2),
            },
        }
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{request.key}.json"
        path.write_text(json.dumps(recording, indent=2, ensure_ascii=False) + "\n")
        return result
