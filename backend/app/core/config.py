from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.llm.facade import LLMPrices

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """App settings, read from the environment (prefix `FORMPILOT_`) or `backend/.env`."""

    model_config = SettingsConfigDict(env_prefix="FORMPILOT_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://formpilot:formpilot@localhost:5432/formpilot"
    data_dir: Path = REPO_ROOT / "data"
    # Stand-in for the external source the tender forms come from in the real product.
    seed_forms_dir: Path = REPO_ROOT / "forms"
    # "hash": deterministic test embedder, never loads the model (tests/conftest.py).
    embedder: Literal["fastembed", "hash"] = "fastembed"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Slug of the tenant every request acts for, until real authentication (tenants/service.py).
    current_tenant: str = "alpenlogic"
    # Development helpers (POST /dev/reset): off unless set, `make dev` turns them on.
    dev_tools: bool = False

    # "fake": replays recorded answers (llm_recordings_dir), no key and no network (tests, e2e).
    llm_provider: Literal["openai", "fake"] = "fake"
    # "recorded": a replay takes the time of the recorded call; "none": instant (tests, e2e).
    fake_llm_latency: Literal["recorded", "none"] = "recorded"
    llm_model: str = "gpt-5-mini"
    llm_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "low"
    llm_recordings_dir: Path = REPO_ROOT / "backend" / "llm_recordings"
    # US dollars per million tokens, for the cost in the logs: gpt-5-mini, Standard tier
    # (https://developers.openai.com/api/docs/pricing, checked 2026-11-04). Update with the model.
    llm_price_input: float = 0.25
    llm_price_cached_input: float = 0.025
    llm_price_output: float = 2.0
    # Model calls of a fill run at the same time (one per call group, see filling/groups.py).
    fill_max_parallel_calls: int = 10
    # Average time of one model call, for the estimate shown before a fill.
    fill_seconds_per_call: int = 25
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "FORMPILOT_OPENAI_API_KEY"),
    )

    def llm_prices(self) -> LLMPrices:
        from app.llm.facade import LLMPrices

        return LLMPrices(
            input=self.llm_price_input,
            cached_input=self.llm_price_cached_input,
            output=self.llm_price_output,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
