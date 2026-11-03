# Backend

Python 3.14 · FastAPI (native SSE via `fastapi.sse`) · SQLAlchemy 2.1 + psycopg 3 · Alembic · PostgreSQL 18 + pgvector 0.8 (Docker) · fastembed · Anthropic SDK (only in `app/llm/`) · PyMuPDF · python-docx · pytest · uv, ruff, pyright.
Architecture, module rules and data model: `../docs/ARCHITECTURE.md` §3.

| Command | What it does |
|---|---|
| `make db` (repo root) | start PostgreSQL + pgvector and wait until healthy |
| `uv run fastapi dev` | API on :8000 with reload; migrations run at startup (entrypoint in `pyproject.toml`) |
| `uv run pytest` | fast tests, on the `formpilot_test` database (created and migrated by the fixtures) |
| `uv run pytest -m slow` | tests that load the real embedding model |
| `uv run ruff check . && uv run ruff format .` · `uv run pyright` | lint/format · types |
| `uv run alembic revision --autogenerate -m "..."` | new migration (models must be imported in `app/modules/__init__.py`) |

Settings: `app/core/config.py`, env prefix `FORMPILOT_` (or `backend/.env`); `ANTHROPIC_API_KEY` for the real LLM, `FORMPILOT_LLM_PROVIDER=fake` by default.

Conventions: every table uses `TimestampMixin`; `def` path operations by default (`async` only for non-blocking code such as SSE); `Annotated` dependencies (`SessionDep`).

Skills: `fastapi`, `uv`, `pydantic`, `supabase-postgres-best-practices` (Postgres, pgvector, indexes), `claude-api` (global, for `app/llm/`).
The `fastapi` skill prefers SQLModel and ty; this project keeps SQLAlchemy and pyright (validated architecture, ty still in beta).
