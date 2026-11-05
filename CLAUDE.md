# AI form filler

This repository is a technical test for Sealio (Swiss AI SaaS for tenders and RFPs), due Thursday, November 5.

## Product

### Context

Besides a written proposal (Word or PowerPoint), buyers often send forms
that bidders must fill in: company information, insurance, tax and legal
declarations. Filling a form by hand takes hours, while most answers
already exist somewhere in the company's documents.

The goal is to build the feature that lets a user fill in forms like these
with AI. The user clicks on the file; the following screens, buttons and
steps are up to us.

Two real forms from a Swiss public tender are in `forms/` (Annex 4 in Word,
Annex 7 in PDF).

Constraints:
    - Runs on localhost. No deployment, no real login.
    - We invent the bidder company and its knowledge base.

### Priorities

1. A clear, smooth user flow
2. Reliable AI: answers grounded in the company's documents, with sources,
   no invented answers, a human in the loop where it matters
3. The filled form exported in its original format and layout

This is an MVP built in 3-4 days, and it must work end to end. Secondary
features (monitoring, metrics, ...) go in a "Remaining features" section
of the README and are implemented only if time allows.

Testing is not secondary: the critical parts (form parsing, answer
validation, export to the original format) must be covered by tests.

### Product decisions (current state)

- One fictitious tender (Cloud Platform Services – Canton of Zurich) holding both forms; bidder Alpenlogic AG.
- Flow: Company knowledge → Tender → Setup (modal) → Live fill → Export. Details in `docs/USER_FLOW.md`, mockups in `docs/design/`.
- No form- or field-specific rules: the AI decides per field using generic criteria (verified evidence, conflicting sources, outdated source, user-only field).
- Yes/No declarations are auto-ticked when evidence is found (proof shown, editable), left empty otherwise. Signature and stamp are never filled.
- A value from a source over a year old with no validity still running is proposed as outdated (to check). A Yes/No whose rule does not apply to the bidder is left empty.
- Export is allowed with a warning for empty fields and doubts; only an unanswered declaration blocks it. Export in the original format only.
- Product vocabulary: the interface never says "AI" ("Auto-fill", "Filling the form…", "Filled automatically", no ✦ icon).
- Answers appear field by field while the model writes (OpenAI streaming in the LLM facade; each field is validated and published as soon as it is complete). No re-run of the auto-fill on a started form: "Discard answers" (deletes all answers, the user's included, also during a running fill) then Auto-fill again; a better re-run that keeps the user's values is for a V2. The Source tab of Live fill comes with step 7 (review).
- AI: OpenAI `gpt-5-mini` via an LLM facade (`FakeLLM` replays recorded answers in tests and e2e, simulating the recorded latency unless `FORMPILOT_FAKE_LLM_LATENCY=none`, as tests and e2e do; cost and timing of each fill logged; pricing in `backend/CLAUDE.md`, ~$0.005 per Annex 7 fill); hybrid RAG in PostgreSQL (local fastembed embeddings in pgvector + full-text search); one LLM call per group of fields, made twice and merged (~$0.06 and ~28 s per Annex 4 fill). V1 has no fact extraction at ingestion: Company knowledge lists documents only, and doubts (conflict, outdated) are detected during filling.
- Architecture (global, front, back): `docs/ARCHITECTURE.md`. Frontend tests follow the `screen-tests` skill (Vitest screen integration tests + one Playwright e2e for the main scenario).
- Project plan and decision log: `docs/PLAN.md`.
- Company knowledge V1: not seeded, it starts empty; the user (in the demo and in the e2e scenario) adds the documents, the demo ones being in `knowledge-base/documents/`. Added with the button or by drag and drop, indexed in the background (passages of one page and one section, hybrid search fused by RRF; a deterministic hash embedder in fast tests), same file name = replacement; deleted with confirmation. Clicking a document previews it page by page (PDF and Word), download kept.
- Word forms (Annex 4) are parsed at seed by a generic DOCX parser (49 fields), filled in Live fill on a docx-preview rendering laid out as on paper (A4 pages, the document's fallback fonts, page numbers) and exported as DOCX. Yes/No declarations are answered with Yes / No buttons (stored `yes` / `no`). Auto-filled like PDF forms: one call per group of fields (a section, cut beyond 10 fields), groups run in parallel, each call made twice and merged (what differs between the two runs becomes a doubt: conflict or `unsure`, shown "To check").
- Tender forms are not uploaded by the user: in the product they come from an external source, so the tender and its two annexes are already present (seeded by the back at startup).
- Multi-tenant ready: tenders, forms and detected fields are shared; each tenant (bidder company) has one `form_fill` per form holding its status and answers (colleagues share it). No login yet: every request acts for the seeded tenant (Alpenlogic AG) through the `CurrentTenantId` dependency.

## Stack and commands

- Monorepo: `frontend/` (Next.js 16.4, React 19, TanStack Query, Tailwind 4 + shadcn/ui `base-nova`, Vitest + MSW 3, Playwright; pnpm 12) and `backend/` (Python 3.14, FastAPI with native SSE, SQLAlchemy 2.1 + Alembic, PostgreSQL 18 + pgvector 0.8 in Docker; uv, ruff, pyright, pytest). Node 26 LTS pinned in `.nvmrc`.
- One command: `make dev` (db + API on :8000 + UI on :3000). Also `make test`, `make test-slow`, `make lint`, `make typecheck`, `make gen-api` (regenerates the front's TS types from the API's OpenAPI), `make db-schema` (regenerates `docs/DB_SCHEMA.md`, checked by a test).
- Each app has its own `CLAUDE.md` with commands and conventions. Project skills in `.claude/skills/` (Next.js: `next-dev-loop`, `shadcn`, Vercel React; back: `fastapi`, `uv`, `pydantic`, `supabase-postgres-best-practices`; tests: `screen-tests`).

## How we work

    - Work in small steps, with tests for the critical parts, and commit as we go
    - When a something is unclear, ask me instead of guessing.
    - Keep this file up to date as decisions are made and add sections if needed, so it always reflects the current state of the project. Ask for validation when upating this file.
