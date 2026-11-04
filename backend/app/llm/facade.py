"""The only door to a language model. No other module imports a provider SDK.

A request asks for an answer shaped by a Pydantic model (structured output). Its `key` names the
call in a stable way (form + section), so a recorded answer can be replayed by `FakeLLM` whatever
passages the search returned that time (the prompt itself depends on the embedder).
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel

from app.core.config import get_settings


@dataclass(frozen=True)
class LLMRequest[T: BaseModel]:
    key: str
    instructions: str
    prompt: str
    schema: type[T]


class LLMError(Exception):
    """The model could not give an answer (provider error, refusal, missing recording)."""


class LLM(Protocol):
    def generate_structured[T: BaseModel](self, request: LLMRequest[T]) -> T: ...


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    if settings.llm_provider == "openai":
        from app.llm.openai_adapter import OpenAILLM

        if settings.openai_api_key is None:
            raise LLMError("OPENAI_API_KEY is not set (backend/.env).")
        return OpenAILLM(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model,
            reasoning_effort=settings.llm_reasoning_effort,
        )
    from app.llm.fake_adapter import FakeLLM

    return FakeLLM.from_dir(settings.llm_recordings_dir)
