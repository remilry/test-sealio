"""Give the e2e scenario a clean environment: an empty database and an empty data folder.

Run by Playwright before it starts the e2e back (frontend/playwright.config.ts), with the e2e
settings in the environment (FORMPILOT_DATABASE_URL, FORMPILOT_DATA_DIR). The database is dropped
and created again; the app's migrations and seed then run at startup, as on a first install.
Refuses to touch a database whose name does not end with "_e2e": never the dev or test one.
"""

import shutil

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings

E2E_SUFFIX = "_e2e"


def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url)
    database = url.database or ""
    if not database.endswith(E2E_SUFFIX):
        raise SystemExit(f"Refusing to reset {database!r}: e2e databases end with {E2E_SUFFIX!r}.")

    # Connected to the maintenance database: one cannot drop the database one is connected to.
    admin = url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        name = sql.Identifier(database)
        # FORCE: a back left running by an interrupted run must not keep the database alive.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(name))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(name))

    shutil.rmtree(settings.data_dir, ignore_errors=True)
    settings.data_dir.mkdir(parents=True)
    print(f"e2e environment reset: database {database}, data in {settings.data_dir}")


if __name__ == "__main__":
    main()
