"""A model call that fails for a passing reason is made again, a few times, after a pause."""

import logging
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.facade import (
    LLMError,
    LLMRequest,
    LLMResult,
    LLMUsage,
    OnPartial,
    TransientLLMError,
)
from app.llm.retrying import RetryingLLM


class Answer(BaseModel):
    value: str


REQUEST = LLMRequest(key="k", instructions="Be exact.", prompt="Which value?", schema=Answer)


class Scripted:
    """Raises the given errors, one per call, then answers; streams `partials` on each call."""

    def __init__(self, errors: list[LLMError], partials: list[dict[str, Any]] | None = None):
        self.errors = list(errors)
        self.partials = partials or []
        self.calls = 0

    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        self.calls += 1
        for partial in self.partials:
            if on_partial is not None:
                on_partial({**partial, "attempt": self.calls})
        if self.errors:
            raise self.errors.pop(0)
        return LLMResult(output=request.schema.model_validate({"value": "ok"}), usage=LLMUsage())


def retrying(inner: Scripted, sleeps: list[float]) -> RetryingLLM:
    return RetryingLLM(inner, attempts=3, base_seconds=2.0, sleep=sleeps.append, jitter=lambda: 0)


def test_a_transient_error_is_retried_until_it_succeeds() -> None:
    inner, sleeps = Scripted([TransientLLMError("timeout"), TransientLLMError("reset")]), []

    result = retrying(inner, sleeps).generate_structured(REQUEST)

    assert result.output == Answer(value="ok")
    assert inner.calls == 3
    assert sleeps == [2.0, 4.0]


def test_it_gives_up_after_the_last_attempt() -> None:
    inner = Scripted([TransientLLMError("1"), TransientLLMError("2"), TransientLLMError("3")])

    with pytest.raises(TransientLLMError, match="3"):
        retrying(inner, []).generate_structured(REQUEST)
    assert inner.calls == 3


def test_a_permanent_error_is_not_retried() -> None:
    inner, sleeps = Scripted([LLMError("No recorded answer for 'k'")]), []

    with pytest.raises(LLMError, match="No recorded answer"):
        retrying(inner, sleeps).generate_structured(REQUEST)
    assert (inner.calls, sleeps) == (1, [])


def test_retry_after_is_honoured_up_to_30_seconds() -> None:
    inner, sleeps = (
        Scripted(
            [
                TransientLLMError("rate", retry_after=7),
                TransientLLMError("rate", retry_after=120),
            ]
        ),
        [],
    )

    retrying(inner, sleeps).generate_structured(REQUEST)

    # Too long a wait is not worth it: the usual pause instead.
    assert sleeps == [7, 4.0]


def test_each_attempt_streams_from_scratch() -> None:
    inner = Scripted([TransientLLMError("cut")], partials=[{"fields": []}, {"fields": [1]}])
    seen: list[dict[str, Any]] = []

    retrying(inner, []).generate_structured(REQUEST, seen.append)

    assert seen == [
        {"fields": [], "attempt": 1},
        {"fields": [1], "attempt": 1},
        {"fields": [], "attempt": 2},
        {"fields": [1], "attempt": 2},
    ]


def test_each_failed_attempt_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    inner = Scripted([TransientLLMError("connection reset")])

    with caplog.at_level(logging.WARNING, logger="app.llm.retrying"):
        retrying(inner, []).generate_structured(REQUEST)

    assert "attempt 1 of 3" in caplog.text
    assert "connection reset" in caplog.text
