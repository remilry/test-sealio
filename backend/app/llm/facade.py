"""The only door to a language model. No other module imports a provider SDK.

A request asks for an answer shaped by a Pydantic model (structured output). Its `key` names the
call in a stable way (form + section), so a recorded answer can be replayed by `FakeLLM` whatever
passages the search returned that time (the prompt itself depends on the embedder). Every answer
comes with what it cost (tokens, dollars) and how long it took, for the logs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.config import get_settings


@dataclass(frozen=True)
class LLMRequest[T: BaseModel]:
    key: str
    instructions: str
    prompt: str
    schema: type[T]


@dataclass(frozen=True)
class LLMUsage:
    """What one or more calls consumed. Cached input tokens are part of the input tokens,
    reasoning tokens part of the output tokens (as the providers count them)."""

    calls: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0

    def __add__(self, other: LLMUsage) -> LLMUsage:
        return LLMUsage(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            seconds=self.seconds + other.seconds,
        )

    def describe(self) -> str:
        return (
            f"{self.calls} call(s), {self.seconds:.1f}s, ${self.cost_usd:.4f} "
            f"(input {self.input_tokens} tokens incl. {self.cached_input_tokens} cached, "
            f"output {self.output_tokens} incl. {self.reasoning_tokens} reasoning)"
        )


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    usage: LLMUsage


@dataclass(frozen=True)
class LLMPrices:
    """US dollars per million tokens."""

    input: float
    cached_input: float
    output: float

    def cost(self, *, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> float:
        uncached = input_tokens - cached_input_tokens
        return (
            uncached * self.input
            + cached_input_tokens * self.cached_input
            + output_tokens * self.output
        ) / 1_000_000


class LLMError(Exception):
    """The model could not give an answer (provider error, refusal, missing recording)."""


class TransientLLMError(LLMError):
    """A failure that may pass (connection cut, timeout, rate limit, server error, an answer that
    could not be read): worth another try. `retry_after` is the wait the provider asked for."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


# Receives the output parsed so far (a JSON object, possibly incomplete).
OnPartial = Callable[[dict[str, Any]], None]


class LLM(Protocol):
    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        """`on_partial` is called several times, in order, with the output so far."""
        ...


@lru_cache
def get_llm() -> LLM:
    """The configured model, its passing failures retried (RetryingLLM)."""
    from app.llm.retrying import RetryingLLM

    settings = get_settings()
    return RetryingLLM(
        _provider(),
        attempts=settings.llm_attempts,
        base_seconds=settings.llm_retry_base_seconds,
    )


def _provider() -> LLM:
    settings = get_settings()
    if settings.llm_provider == "openai":
        from app.llm.openai_adapter import OpenAILLM

        if settings.openai_api_key is None:
            raise LLMError("OPENAI_API_KEY is not set (backend/.env).")
        return OpenAILLM(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model,
            reasoning_effort=settings.llm_reasoning_effort,
            prices=settings.llm_prices(),
        )
    from app.llm.fake_adapter import FakeLLM

    return FakeLLM.from_dir(
        settings.llm_recordings_dir,
        latency=settings.fake_llm_latency,
        failures=settings.fake_llm_failures,
    )
