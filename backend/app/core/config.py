from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # "fake": replays recorded answers (llm_recordings_dir), no key and no network (tests, e2e).
    llm_provider: Literal["openai", "fake"] = "fake"
    llm_model: str = "gpt-5-mini"
    llm_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "low"
    llm_recordings_dir: Path = REPO_ROOT / "backend" / "llm_recordings"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "FORMPILOT_OPENAI_API_KEY"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
