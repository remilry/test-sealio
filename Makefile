.PHONY: install db db-stop dev dev-back dev-front test test-slow test-all test-back test-front e2e lint typecheck format gen-api db-schema

BACK = cd backend &&
FRONT = cd frontend &&

install:            ## Install back and front dependencies
	$(BACK) uv sync
	$(FRONT) pnpm install

db:                 ## Start PostgreSQL + pgvector (Docker) and wait until healthy
	docker compose up -d --wait db

db-stop:
	docker compose stop db

dev: db             ## Run the whole app: db, API on :8000, UI on :3000 (Ctrl-C stops both)
	$(MAKE) -j2 dev-back dev-front

dev-back:
	$(BACK) uv run fastapi dev

dev-front:
	$(FRONT) pnpm dev

test: test-back test-front   ## Fast tests (no embedding model)

test-back: db
	$(BACK) uv run pytest

test-front:
	$(FRONT) pnpm test

test-slow: db       ## Tests that load the real embedding model
	$(BACK) uv run pytest -m slow

test-all: db test-front
	$(BACK) uv run pytest -m ""

e2e: db             ## Playwright main scenario
	$(FRONT) pnpm e2e

lint:
	$(BACK) uv run ruff check . && uv run ruff format --check .
	$(FRONT) pnpm lint && pnpm format:check

typecheck:
	$(BACK) uv run pyright
	$(FRONT) pnpm typecheck

format:
	$(BACK) uv run ruff format . && uv run ruff check --fix .
	$(FRONT) pnpm format

gen-api:            ## Regenerate frontend types from the running API's OpenAPI
	$(FRONT) pnpm gen:api

db-schema:          ## Regenerate docs/DB_SCHEMA.md (Mermaid diagram) from the SQLAlchemy models
	$(BACK) uv run python -m scripts.db_schema
