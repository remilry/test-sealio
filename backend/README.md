# Formpilot — backend

FastAPI API for the AI form filler. Commands: see `CLAUDE.md` in this folder; architecture: `../docs/ARCHITECTURE.md`.

```bash
make db            # from the repo root: PostgreSQL + pgvector in Docker
uv sync
uv run fastapi dev # http://localhost:8000/docs
```
