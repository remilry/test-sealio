from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]


def upgrade_to_head(database_url: str) -> None:
    """Apply all Alembic migrations (run at startup and by the test fixtures)."""
    config = Config(toml_file=str(BACKEND_DIR / "pyproject.toml"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
