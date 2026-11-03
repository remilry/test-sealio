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
    cors_origins: list[str] = ["http://localhost:3000"]

    llm_provider: Literal["anthropic", "fake"] = "fake"
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "FORMPILOT_ANTHROPIC_API_KEY"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
