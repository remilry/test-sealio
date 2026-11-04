"""OpenAI adapter: Responses API with a strict JSON schema derived from the Pydantic model."""

import time
from typing import Any, Literal

import openai
from openai.types.responses import ResponseUsage
from pydantic import BaseModel
from pydantic_core import from_json

from app.llm.facade import LLMError, LLMPrices, LLMRequest, LLMResult, LLMUsage, OnPartial


class OpenAILLM:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        reasoning_effort: Literal["minimal", "low", "medium", "high"],
        prices: LLMPrices,
    ) -> None:
        self._client = openai.OpenAI(api_key=api_key, timeout=120.0, max_retries=2)
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
                            on_partial(partial)
                response = stream.get_final_response()
        except openai.APIError as error:
            raise LLMError(f"The language model failed: {error}") from error
        parsed = response.output_parsed
        if parsed is None:
            raise LLMError("The language model returned no usable answer.")
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


def _parse_partial(text: str) -> dict[str, Any] | None:
    try:
        value = from_json(text, allow_partial=True)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
