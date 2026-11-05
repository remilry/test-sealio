"""Model calls made again when they fail for a reason that may pass (`TransientLLMError`).

Each attempt streams from scratch: `on_partial` sees the new attempt's output from its start
(the answer engine keeps the fields it already published and ignores them the second time).
"""

import logging
import random
import time
from collections.abc import Callable

from pydantic import BaseModel

from app.llm.facade import LLM, LLMRequest, LLMResult, OnPartial, TransientLLMError

logger = logging.getLogger(__name__)

# A longer wait asked by the provider is not worth it: the usual pause instead.
MAX_RETRY_AFTER_SECONDS = 30.0


class RetryingLLM:
    def __init__(
        self,
        llm: LLM,
        *,
        attempts: int,
        base_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._llm = llm
        self._attempts = max(attempts, 1)
        self._base_seconds = base_seconds
        self._sleep = sleep
        self._jitter = jitter

    def generate_structured[T: BaseModel](
        self, request: LLMRequest[T], on_partial: OnPartial | None = None
    ) -> LLMResult[T]:
        for attempt in range(1, self._attempts + 1):
            try:
                return self._llm.generate_structured(request, on_partial)
            except TransientLLMError as error:
                logger.warning(
                    "Model call %r failed, attempt %s of %s: %s",
                    request.key,
                    attempt,
                    self._attempts,
                    error,
                )
                if attempt == self._attempts:
                    raise
                self._sleep(self._pause(attempt, error.retry_after))
        raise AssertionError("unreachable")

    def _pause(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None and 0 <= retry_after <= MAX_RETRY_AFTER_SECONDS:
            return retry_after
        return self._base_seconds * 2 ** (attempt - 1) * (1 + 0.25 * self._jitter())
