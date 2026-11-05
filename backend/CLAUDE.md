# Backend

Python 3.14 · FastAPI (native SSE via `fastapi.sse`) · SQLAlchemy 2.1 + psycopg 3 · Alembic · PostgreSQL 18 + pgvector 0.8 (Docker) · fastembed · OpenAI SDK (only in `app/llm/`) · PyMuPDF · python-docx · pytest · uv, ruff, pyright.
Architecture, module rules and data model: `../docs/ARCHITECTURE.md` §3.

| Command | What it does |
|---|---|
| `make db` (repo root) | start PostgreSQL + pgvector and wait until healthy |
| `uv run fastapi dev` | API on :8000 with reload; migrations run at startup (entrypoint in `pyproject.toml`) |
| `uv run pytest` | fast tests, on the `formpilot_test` database (created and migrated by the fixtures) |
| `uv run pytest -m slow` | tests that load the real embedding model |
| `uv run ruff check . && uv run ruff format .` · `uv run pyright` | lint/format · types |
| `uv run python -m scripts.record_llm [--add-demo-documents] [--form annex-4] [--replay]` | record the real model's answers for `FakeLLM` (dev database, needs `OPENAI_API_KEY`, prints cost, timing and the check against `GROUND_TRUTH.md`: OK / flagged / silent); `--form` one form only, `--replay` replays the saved recordings for free |
| `make eval` · `make eval-live RUNS=n FORM=annex-4` · `make eval-report` (repo root) | score the answers against `GROUND_TRUTH.md` (`scripts/evaluate.py`, own database `formpilot_eval` + `data-eval/`, demo documents added there): recordings replayed (free), or the real model (paid, each run saved in `eval_runs/`), then `docs/EVALUATION.md` written from the saved runs |
| `uv run alembic revision --autogenerate -m "..."` | new migration (models must be imported in `app/modules/__init__.py`) |

Settings: `app/core/config.py`, env prefix `FORMPILOT_` (or `backend/.env`); `OPENAI_API_KEY` for the real LLM (with `FORMPILOT_LLM_PROVIDER=openai`), `fake` by default (replays `llm_recordings/`). `FORMPILOT_FAKE_LLM_LATENCY` = `recorded` (default: `FakeLLM` sleeps like the recorded call, from the `timing` block of the recording) or `none` (instant; set by the tests and the e2e). `FORMPILOT_DEV_TOOLS=true` (set by `make dev`) enables `POST /dev/reset` (back to the start of the demo: no company document, every form not started), used by the front's floating "Reset demo" button shown in `next dev` only; off, the route answers 404. `FORMPILOT_FILL_MAX_PARALLEL_CALLS` (10: call groups run at once) and `FORMPILOT_FILL_RUNS_PER_CALL` (2: each call made twice and merged, what differs becomes a doubt) shape the fill; `FORMPILOT_FILL_SECONDS_PER_CALL` (30) the duration shown in Setup. Retries: `FORMPILOT_LLM_ATTEMPTS` (3: a model call failing for a passing reason — cut stream, timeout, 429, 5xx, unreadable answer — is tried again, `RetryingLLM` in `get_llm()`), `FORMPILOT_LLM_RETRY_BASE_SECONDS` (2, doubled each time; 0 in tests and e2e), `FORMPILOT_LLM_CALL_TIMEOUT_SECONDS` (90 per attempt; the SDK no longer retries itself), `FORMPILOT_INDEX_ATTEMPTS` (3) and `FORMPILOT_INDEX_RETRY_SECONDS` (1) for indexing a document. `FORMPILOT_FAKE_LLM_FAILURES` (JSON `{"<key prefix>": n}`) makes `FakeLLM` fail n times first (e2e of Retry). Model, reasoning effort and per-token prices are settings too (`FORMPILOT_LLM_MODEL`, `FORMPILOT_LLM_REASONING_EFFORT`, `FORMPILOT_LLM_PRICE_INPUT` / `_CACHED_INPUT` / `_OUTPUT`).

LLM pricing (`gpt-5-mini`, Standard tier, US$ per 1M tokens, [source](https://developers.openai.com/api/docs/pricing), checked 2026-11-04): input 0.25 · cached input 0.025 · output 2.00 (reasoning tokens billed as output). Batch/Flex are half price but slower, Fast (ex-priority) costs 1.8×. Measured with streaming: an Annex 7 fill = 1 call, first field after ~7 s, done after ~17 s, ~$0.003–0.005 (recorded with one run). An Annex 4 fill = 9 groups × 2 runs = 18 calls in parallel, ~28 s, ~$0.06 (one run: ~$0.03; effort `medium`: twice the cost and time, no better). Each fill logs its cost and timing (`app.modules.filling.job`); update the price settings when the model changes. Never read `backend/.env`.

Conventions: every table uses `TimestampMixin`; `def` path operations by default (`async` only for non-blocking code such as SSE); `Annotated` dependencies (`SessionDep`).

Skills: `fastapi`, `uv`, `pydantic`, `supabase-postgres-best-practices` (Postgres, pgvector, indexes).
The `fastapi` skill prefers SQLModel and ty; this project keeps SQLAlchemy and pyright (validated architecture, ty still in beta).
