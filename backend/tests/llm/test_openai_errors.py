"""The OpenAI adapter tells a passing failure (worth another try) from one that will not pass."""

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import httpx2 as httpx
import openai
import pytest
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.llm.facade import LLMError, LLMPrices, LLMRequest, TransientLLMError
from app.llm.openai_adapter import OpenAILLM


class Answer(BaseModel):
    value: str


REQUEST = LLMRequest(key="k", instructions="Be exact.", prompt="Which value?", schema=Answer)
HTTP_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")


def response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, request=HTTP_REQUEST, headers=headers)


def adapter() -> OpenAILLM:
    return OpenAILLM(
        api_key="sk-test", model="gpt-5-mini", reasoning_effort="low", prices=LLMPrices(0, 0, 0)
    )


def failing_with(error: Exception) -> Callable[..., Any]:
    def stream(**_kwargs: Any) -> Any:
        raise error

    return stream


class _Stream:
    """What `responses.stream(...)` gives: a context manager, iterated (no event here), then the
    final response."""

    def __init__(self, parsed: Answer | None, raises: Exception | None) -> None:
        self._parsed, self._raises = parsed, raises

    def __enter__(self) -> _Stream:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __iter__(self) -> Iterator[Any]:
        return iter(())

    def get_final_response(self) -> Any:
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(output_parsed=self._parsed, usage=None)


def answering(parsed: Answer | None, *, raises: Exception | None = None) -> Callable[..., Any]:
    return lambda **_kwargs: _Stream(parsed, raises)


def call_with(stream: Callable[..., Any]) -> None:
    llm = adapter()
    llm._client.responses.stream = stream  # type: ignore[method-assign]
    llm.generate_structured(REQUEST)


def _validation_error() -> ValidationError:
    try:
        Answer.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("unreachable")


@pytest.mark.parametrize(
    "error",
    [
        openai.APIConnectionError(request=HTTP_REQUEST),
        openai.APITimeoutError(request=HTTP_REQUEST),
        openai.RateLimitError("slow down", response=response(429), body=None),
        openai.InternalServerError("oops", response=response(500), body=None),
    ],
    ids=["connection", "timeout", "rate-limit", "server"],
)
def test_passing_provider_failures_are_transient(error: Exception) -> None:
    with pytest.raises(TransientLLMError):
        call_with(failing_with(error))


@pytest.mark.parametrize(
    "error",
    [
        openai.AuthenticationError("bad key", response=response(401), body=None),
        openai.BadRequestError("bad request", response=response(400), body=None),
        openai.PermissionDeniedError("denied", response=response(403), body=None),
    ],
    ids=["auth", "bad-request", "denied"],
)
def test_failures_that_will_not_pass_are_not_transient(error: Exception) -> None:
    with pytest.raises(LLMError) as raised:
        call_with(failing_with(error))
    assert not isinstance(raised.value, TransientLLMError)


def test_retry_after_is_read_from_a_rate_limit() -> None:
    error = openai.RateLimitError(
        "slow down", response=response(429, {"retry-after": "7"}), body=None
    )

    with pytest.raises(TransientLLMError) as raised:
        call_with(failing_with(error))

    assert raised.value.retry_after == 7


def test_no_usable_answer_is_transient() -> None:
    with pytest.raises(TransientLLMError):
        call_with(answering(None))


@pytest.mark.parametrize("error", [_validation_error(), ValueError("bad JSON")])
def test_an_answer_that_cannot_be_read_is_transient(error: Exception) -> None:
    with pytest.raises(TransientLLMError):
        call_with(answering(None, raises=error))


def test_the_sdk_does_not_retry_on_its_own_and_calls_are_bounded() -> None:
    client = adapter()._client

    assert client.max_retries == 0
    assert client.timeout == get_settings().llm_call_timeout_seconds == 90.0
