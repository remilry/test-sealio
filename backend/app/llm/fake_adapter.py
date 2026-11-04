"""Deterministic stand-ins for the real model: no key, no network.

`FakeLLM` replays answers by request key: recorded from the real model (`RecordingLLM`, see
scripts/record_llm.py) into `<key>.json` files, or given directly by a test.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.llm.facade import LLM, LLMError, LLMRequest, LLMResult, LLMUsage


class FakeLLM:
    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self._answers = answers
        # Every request received, for tests to look at the prompts.
        self.requests: list[LLMRequest[Any]] = []

    @classmethod
    def from_dir(cls, directory: Path) -> FakeLLM:
        return cls({path.stem: json.loads(path.read_text()) for path in directory.glob("*.json")})

    def generate_structured[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        self.requests.append(request)
        answer = self._answers.get(request.key)
        if answer is None:
            raise LLMError(f"No recorded answer for {request.key!r} (scripts/record_llm.py).")
        # A replay costs nothing and takes no time.
        return LLMResult(output=request.schema.model_validate(answer), usage=LLMUsage(calls=1))


class RecordingLLM:
    """Calls a real model and writes each answer to `<directory>/<key>.json` for FakeLLM."""

    def __init__(self, llm: LLM, directory: Path) -> None:
        self._llm = llm
        self._directory = directory

    def generate_structured[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        result = self._llm.generate_structured(request)
        answer = result.output
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{request.key}.json"
        path.write_text(
            json.dumps(answer.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        )
        return result
