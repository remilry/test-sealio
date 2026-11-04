"""OpenAI adapter: Responses API with a strict JSON schema derived from the Pydantic model."""

from typing import Literal

import openai
from pydantic import BaseModel

from app.llm.facade import LLMError, LLMRequest


class OpenAILLM:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        reasoning_effort: Literal["minimal", "low", "medium", "high"],
    ) -> None:
        self._client = openai.OpenAI(api_key=api_key, timeout=120.0, max_retries=2)
        self._model = model
        self._effort: Literal["minimal", "low", "medium", "high"] = reasoning_effort

    def generate_structured[T: BaseModel](self, request: LLMRequest[T]) -> T:
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=request.instructions,
                input=request.prompt,
                text_format=request.schema,
                reasoning={"effort": self._effort},
                # Nothing is kept on OpenAI's side: every call is self-contained.
                store=False,
            )
        except openai.APIError as error:
            raise LLMError(f"The language model failed: {error}") from error
        parsed = response.output_parsed
        if parsed is None:
            raise LLMError("The language model returned no usable answer.")
        return parsed
