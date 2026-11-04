import pytest

from app.core.config import get_settings
from scripts import reset_e2e


def test_the_e2e_reset_never_touches_a_database_not_named_for_e2e(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "FORMPILOT_DATABASE_URL", "postgresql+psycopg://formpilot:formpilot@localhost/formpilot"
    )
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit, match="Refusing to reset 'formpilot'"):
            reset_e2e.main()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
