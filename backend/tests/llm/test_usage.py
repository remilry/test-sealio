"""Cost and usage of the model calls, as logged (no network)."""

import pytest
from openai.types.responses import ResponseUsage

from app.llm.facade import LLMPrices, LLMUsage
from app.llm.openai_adapter import OpenAILLM

PRICES = LLMPrices(input=0.25, cached_input=0.025, output=2.0)


def test_cached_input_tokens_are_billed_at_the_cached_price() -> None:
    cost = PRICES.cost(input_tokens=10_000, cached_input_tokens=4_000, output_tokens=1_000)

    # 6,000 x 0.25 + 4,000 x 0.025 + 1,000 x 2.0, per million.
    assert cost == pytest.approx(0.0036)


def test_usages_add_up_over_sections() -> None:
    total = LLMUsage(1, 100, 10, 50, 20, 0.001, 1.5) + LLMUsage(1, 200, 0, 70, 30, 0.002, 2.0)

    assert (total.calls, total.input_tokens, total.cached_input_tokens) == (2, 300, 10)
    assert (total.output_tokens, total.reasoning_tokens, total.seconds) == (120, 50, 3.5)
    assert total.cost_usd == pytest.approx(0.003)
    assert total.describe().startswith("2 call(s), 3.5s, $0.0030 (input 300 tokens incl. 10")


def test_the_openai_usage_becomes_tokens_cost_and_time() -> None:
    llm = OpenAILLM(api_key="test", model="gpt-5-mini", reasoning_effort="low", prices=PRICES)
    usage = ResponseUsage.model_validate(
        {
            "input_tokens": 12_000,
            "input_tokens_details": {"cached_tokens": 2_000, "cache_write_tokens": 0},
            "output_tokens": 3_000,
            "output_tokens_details": {"reasoning_tokens": 1_800},
            "total_tokens": 15_000,
        }
    )

    result = llm._usage(usage, started=0.0)

    assert (result.calls, result.input_tokens, result.cached_input_tokens) == (1, 12_000, 2_000)
    assert (result.output_tokens, result.reasoning_tokens) == (3_000, 1_800)
    assert result.cost_usd == pytest.approx((10_000 * 0.25 + 2_000 * 0.025 + 3_000 * 2.0) / 1e6)
    assert result.seconds > 0
