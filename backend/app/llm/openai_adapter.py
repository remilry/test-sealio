"""OpenAI adapter: Responses API with a strict JSON schema derived from the Pydantic model."""

import time
from typing import Any, Literal

import openai
from openai.types.responses import ResponseUsage
from pydantic import BaseModel
from pydantic_core import from_json

from app.core.config import get_settings
from app.llm.facade import (
    LLMError,
    LLMPrices,
    LLMRequest,
    LLMResult,
    LLMUsage,
    OnPartial,
    TransientLLMError,
)


class OpenAILLM:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        reasoning_effort: Literal["minimal", "low", "medium", "high"],
        prices: LLMPrices,
        timeout_seconds: float | None = None,
    ) -> None:
        # No retry of the SDK's own: RetryingLLM retries every passing failure, the cut stream
        # included (the SDK only retries before the answer starts).
        self._client = openai.OpenAI(
            api_key=api_key,
            timeout=timeout_seconds or get_settings().llm_call_timeout_seconds,
            max_retries=0,
        )
        self._model = model
        self._effort: Literal["minimal", "low", "medium", "high"] = reasoning_effort
        self._prices = prices

    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        started = time.monotonic()
        try:
            with self._client.responses.stream(
                model=self._model,
                instructions=request.instructions,
                input=request.prompt,
                text_format=request.schema,
                reasoning={"effort": self._effort},
                # Nothing is kept on OpenAI's side: every call is self-contained.
                store=False,
            ) as stream:
                text = ""
                for event in stream:
                    if event.type != "response.output_text.delta":
                        continue
                    text += event.delta
                    if on_partial is not None:
                        partial = _parse_partial(text)
                        if partial:
                            _forward(on_partial, partial)
                response = stream.get_final_response()
        except _CallerError as error:
            # Raised by the caller's own code, not the model's: as it is, never retried.
            raise error.original from None
        except (
            openai.APIConnectionError,  # APITimeoutError included
            openai.RateLimitError,
            openai.InternalServerError,
        ) as error:
            raise TransientLLMError(
                f"The language model failed: {error}", retry_after=_retry_after(error)
            ) from error
        except openai.APIError as error:
            raise LLMError(f"The language model failed: {error}") from error
        except ValueError as error:
            # Unreadable output (pydantic's ValidationError is a ValueError): another try may do.
            raise TransientLLMError(
                f"The language model's answer could not be read: {error}"
            ) from error
        parsed = response.output_parsed
        if parsed is None:
            raise TransientLLMError("The language model returned no usable answer.")
        return LLMResult(output=parsed, usage=self._usage(response.usage, started))

    def _usage(self, usage: ResponseUsage | None, started: float) -> LLMUsage:
        seconds = time.monotonic() - started
        if usage is None:
            return LLMUsage(calls=1, seconds=seconds)
        cached = usage.input_tokens_details.cached_tokens
        return LLMUsage(
            calls=1,
            input_tokens=usage.input_tokens,
            cached_input_tokens=cached,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
            cost_usd=self._prices.cost(
                input_tokens=usage.input_tokens,
                cached_input_tokens=cached,
                output_tokens=usage.output_tokens,
            ),
            seconds=seconds,
        )


class _CallerError(Exception):
    """Wraps what `on_partial` raised, so the model's error handling below never takes it for
    a failure of the model (a ValueError there would be retried as an unreadable answer)."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


def _forward(on_partial: OnPartial, partial: dict[str, Any]) -> None:
    try:
        on_partial(partial)
    except Exception as error:
        raise _CallerError(error) from error


def _retry_after(error: openai.APIError) -> float | None:
    """The wait in seconds the provider asked for (`Retry-After` header), if any."""
    if not isinstance(error, openai.APIStatusError):
        return None
    try:
        return float(error.response.headers.get("retry-after", ""))
    except ValueError:
        return None


def _parse_partial(text: str) -> dict[str, Any] | None:
    try:
        value = from_json(text, allow_partial=True)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
