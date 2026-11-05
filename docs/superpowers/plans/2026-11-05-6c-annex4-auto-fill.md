# 6c — Annex 4 auto-fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-fill the Word Annex 4 like the Annex 7, with model calls run in parallel per group of fields, heading context for Word fields, and the real model's answers recorded for `FakeLLM`.

**Architecture:** A pure grouping function cuts each section (all fields but signatures) into groups of at most 10; each group is one model call with a stable key. The fill job runs the groups in a bounded thread pool, one DB session per group, publishing each field as soon as it is validated. The Word parser records the heading that covers a field (`context`), used in the search query and the prompt only.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.1 + Alembic, PostgreSQL, python-docx, pytest; Playwright for the e2e.

**Spec:** `docs/superpowers/specs/2026-11-05-6c-annex4-auto-fill-design.md`

## Global Constraints

- No rule specific to the Annex 4 or to a field: parser, prompt and search stay generic.
- Same prompt, same passages per field; a field set by the user is never replaced (5c's conditional upsert).
- Group limit: **10** fields; pool: `fill_max_parallel_calls = 10` (`FORMPILOT_FILL_MAX_PARALLEL_CALLS`); `fill_seconds_per_section` renamed `fill_seconds_per_call` (25).
- Keys: `<form>--<section>` for a single group (unchanged: the Annex 7 recording keeps working), `<form>--<section>--part-<i>` (i from 1) when cut.
- `context` is never exposed by the API nor shown in the UI.
- Interface vocabulary: never "AI" in user-facing text (backend error messages included).
- Paid recordings (Task 5): after **each** attempt, report the cost and the gaps from `GROUND_TRUTH.md` to the user and **wait for their go-ahead** before the next one.
- Commands: `cd backend && uv run pytest`, `uv run ruff check . && uv run ruff format .`, `uv run pyright`; `make db-schema` after a model change; `make test` / `make lint` / `make typecheck` at the end.

## Review Focus

1. **Thread safety of shared objects across groups**: `FakeLLM.generate_structured` must not mutate its stored recordings (`answer.pop("timing")`), and the embedder singleton must be usable from several threads → test in Task 3: the same `FakeLLM` replays two groups concurrently, twice, with identical results.
2. **DB connection pool vs 10 threads + main session + SSE readers**: a 9-group fill must not hang waiting for a connection → Task 3 sizes the engine pool (`pool_size` ≥ `fill_max_parallel_calls` + 5) and the parallel test runs 12 groups with `fill_max_parallel_calls=10`.
3. **A form already started by hand** (the user set some Table 7 fields): groups and keys stay those of the recording, user fields are skipped, a group left empty is not called → test in Task 2 (grouping) and Task 5 (replay after setting two Table 7 fields).
4. **Discard while groups are mid-call**: no answer or event is written after the discard, no "error" event → Task 3 test.
5. **Existing dev database** where Annex 4 was parsed in 6b with answers: startup adds `context` without deleting fields or answers → Task 1 test.

---

### Task 1: Heading context of Word fields

**Files:**
- Modify: `backend/app/modules/forms/parsing/schema.py` (`ParsedField`)
- Modify: `backend/app/modules/forms/parsing/docx_parser.py` (`_table_blanks`, `_Blank`)
- Modify: `backend/app/modules/forms/models.py` (`Field.context`)
- Create: `backend/migrations/versions/<rev>_field_context.py` (autogenerate)
- Modify: `backend/app/modules/forms/service.py` (`_store_schema`, `import_form`)
- Modify: `docs/DB_SCHEMA.md` (`make db-schema`)
- Test: `backend/tests/modules/forms/test_docx_parser.py`, `backend/tests/modules/forms/test_api.py` (or a new `test_seed_context.py`)

**Interfaces:**
- Produces: `ParsedField.context: str | None = None`; `Field.context: Mapped[str | None]` (Text, nullable).

- [ ] **Step 1: Write the failing parser tests** (synthetic Word documents built with python-docx, like the existing rule tests):
  - `test_a_heading_row_is_the_context_of_the_rows_below`: table = heading row "Number of employees" (one merged cell), then a row of 2 labels each with an empty paragraph below → both fields have `context == "Number of employees"`; a second heading row "Other" → fields below it have `context == "Other"`.
  - `test_a_label_heading_labels_on_its_right_is_their_context`: row `["Available amounts per claim:", "Personal injury:\nProperty damage:"]` → the two fields have `context == "Available amounts per claim"`.
  - `test_heading_row_and_heading_label_chain`: both → `context == "Title › Available amounts per claim"`.
  - `test_fields_without_heading_have_no_context`: `context is None`.
  - In the Annex 4 expected-schema test: the 4 Table 4 fields have `context == "Number of employees in the area essential to performing the tendered contract"`; `personal_injury`, `property_damage`, `financial_loss` have `context == "Available amounts per claim"`; every other field `None`.
- [ ] **Step 2: Run** `cd backend && uv run pytest tests/modules/forms/test_docx_parser.py -v` → the new tests FAIL.
- [ ] **Step 3: Implement** in `_table_blanks`: keep `table_heading: str | None` updated on each heading row (`clean_label` of its text, which also collapses the tab); when a cell is skipped because it heads labels on its right, remember its cleaned text as `row_heading` for the next cell of the row; each `_Blank` gets `context = " › ".join(filter(None, [table_heading, row_heading])) or None`. Yes/No rows: no context (header row is not a heading). Pass `context` through to `ParsedField`.
- [ ] **Step 4: Run** the parser tests → PASS.
- [ ] **Step 5: Write the failing store/seed test** `test_startup_adds_the_context_to_an_annex_4_parsed_without_it`: in the test DB, after startup, set `Field.context = None` for Annex 4 and save an answer on `exact_company_name`; run `seed(session, settings)` again → Table 4/5 fields have their context, field ids unchanged, the answer still there.
- [ ] **Step 6: Implement**: `Field.context` column + `uv run alembic revision --autogenerate -m "field context"`; `_store_schema` writes `context`; in `import_form`, when the form is already parsed and has a parser, re-parse and set `context` on existing fields matched by key (only where it differs; nothing deleted). `make db-schema`.
- [ ] **Step 7: Run** `uv run pytest tests/modules/forms tests/test_db_schema_doc.py -v` → PASS; `uv run pyright` clean.
- [ ] **Step 8: Commit** `feat(forms): heading context of Word fields`.

### Task 2: Call groups and context in the answer engine

**Files:**
- Create: `backend/app/modules/filling/groups.py`
- Modify: `backend/app/modules/filling/answer_engine.py` (`FieldToAnswer`, `request_key`, `answer_section`, `_passages`, `_describe_field`)
- Test: `backend/tests/modules/filling/test_groups.py` (new), `backend/tests/modules/filling/test_streaming.py` or a new `test_answer_engine.py`

**Interfaces:**
- Consumes: `Field.context` (Task 1).
- Produces:
  - `FieldToAnswer(id: int, key: str, label: str, kind: FieldKind, context: str | None = None)`; property `query -> str` = `f"{context} {label}"` or `label`.
  - `MAX_FIELDS_PER_CALL = 10`
  - `@dataclass(frozen=True) class CallGroup: section: str; part: int | None; fields: list[FieldToAnswer]` (`part` None when the section is not cut).
  - `call_groups(fields: Sequence[FieldToAnswer], *, skip: Collection[int] = ()) -> list[CallGroup]` — input: all non-signature fields in form order; sections in order of first appearance; a section of n fields → `ceil(n/10)` groups, sizes differing by at most 1, earlier groups larger; then field ids in `skip` are removed; groups left empty are dropped (the others keep their `part`).
  - `request_key(form_file_name: str, section: str, part: int | None = None) -> str` — `--part-{part}` appended when `part` is not None.
  - `answer_section(llm, *, company, form_title, form_file_name, group: CallGroup, search, tender_details, today, on_field=None) -> SectionResult` (replaces `section=` and `fields=`; the prompt's "Section:" line stays `group.section`; key = `request_key(form_file_name, group.section, group.part)`).

- [ ] **Step 1: Write the failing grouping tests** (`test_groups.py`), with fields built as `FieldToAnswer(i, f"f{i}", f"F{i}", FieldKind.TEXT)` in sections:
  - `test_a_section_of_10_fields_is_one_call`: one group, `part is None`.
  - `test_a_section_of_11_fields_is_cut_in_balanced_parts`: sizes `[6, 5]`, parts `[1, 2]`.
  - `test_a_section_of_18_fields_is_cut_in_two_parts_of_9`.
  - `test_sections_keep_their_order`.
  - `test_fields_set_by_the_user_are_skipped_without_moving_others`: 18 fields, skip ids of fields 1 and 2 → part 1 has 7 fields, part 2 has the same 9 as without skip.
  - `test_a_group_left_empty_is_dropped`: skip all of part 2 → only part 1 returned, still `part == 1`.
  - `test_request_key_of_a_part`: `request_key("Annex 4.docx", "Table 7", 2) == "annex-4--table-7--part-2"`; without part unchanged (`"annex-4--table-7"`).
- [ ] **Step 2: Write the failing engine tests**: with a stub `search` that records its queries and `FakeLLM` that captures the request: a field with `context="Available amounts per claim"` and label "Personal injury" → search query `"Available amounts per claim Personal injury"` and prompt line `- key: personal_injury · label: Personal injury · context: Available amounts per claim · kind: text`; a field without context → query = label, line unchanged.
- [ ] **Step 3: Run** `uv run pytest tests/modules/filling -v` → new tests FAIL.
- [ ] **Step 4: Implement** `groups.py` and the engine changes; update the current callers (`job.py`, `scripts/record_llm.py`, existing tests) to build groups with `call_groups` (job still sequential for now: loop over groups).
- [ ] **Step 5: Run** `uv run pytest` (whole backend) → PASS (Annex 7 tests and `test_recorded_answers` unchanged); pyright clean.
- [ ] **Step 6: Commit** `feat(filling): call groups of at most 10 fields, heading context in search and prompt`.

### Task 3: Groups called in parallel in the fill job; duration estimate

**Files:**
- Modify: `backend/app/modules/filling/job.py`
- Modify: `backend/app/core/config.py` (`fill_max_parallel_calls`, `fill_seconds_per_call`)
- Modify: `backend/app/core/db.py` (engine pool size)
- Modify: `backend/app/llm/fake_adapter.py` (only if it mutates stored answers)
- Modify: `backend/app/modules/forms/service.py` (`estimated_fill_seconds`)
- Test: `backend/tests/modules/filling/test_parallel_fill.py` (new), `backend/tests/modules/test_tenders.py` (estimate)

**Interfaces:**
- Consumes: `call_groups`, `CallGroup`, `answer_section(group=...)` (Task 2).
- Produces: `run_groups[T, R](items: Sequence[T], work: Callable[[T], R], *, max_workers: int, stop: threading.Event) -> list[R]` in `job.py` (thread pool; results in input order; on the first exception sets `stop`, skips items not yet started, re-raises it); `Settings.fill_max_parallel_calls: int = 10`, `Settings.fill_seconds_per_call: int = 25`; `estimated_fill_seconds = ceil(len(call_groups(non-signature fields)) / fill_max_parallel_calls) * fill_seconds_per_call`.

- [ ] **Step 1: Write the failing tests** in `test_parallel_fill.py`, on the seeded Annex 4 (the only multi-section form) with a `ScriptedLLM`-style fake keyed by the 9 Annex 4 keys (each answers its fields with "not found" except one quoted value per group, from the demo documents), plus `sleep` latency injected:
  - `test_groups_are_called_in_parallel`: each call sleeps 0.3 s (fake with `sleep`) → total fill < 1.2 s (sequential would be ≥ 2.7 s); `ai_run.status == "done"`; exactly one `done` event; one `answered` event per field to answer; final counts equal `GET /answers` counts.
  - `test_every_field_is_marked_searching_before_any_answer`: all `searching` events precede the first `answered` event.
  - `test_a_failing_group_ends_the_run_with_an_error_and_others_stop_publishing`: one key raises `LLMError` immediately, the others sleep 0.3 s then answer → one `error` event with `MODEL_ERROR`, no `answered` event after it, no `done`.
  - `test_discard_while_groups_are_calling_writes_nothing`: `DELETE /forms/{id}/fill` during the calls → no answers, no `error` event, form `not_started`.
  - `test_the_same_fake_replays_concurrent_calls_identically` (Review Focus 1): run the replay twice in a row → identical answers.
  - `test_twelve_groups_on_ten_workers_finish` (Review Focus 2): `run_groups` with 12 items, `max_workers=10`, each worker opening a `SessionLocal()` and running `SELECT 1` while holding it 0.2 s → 12 results in input order, finishes under 5 s.
  - `test_run_groups_stops_others_on_first_error`: one item raises → `run_groups` re-raises it, `stop` is set, items not yet started are not run.
  - In `test_tenders.py`: Annex 7 `estimated_fill_seconds == 25`; Annex 4 `== 25` (9 groups, 10 parallel); with `fill_max_parallel_calls=4` override → Annex 4 `== 75`.
- [ ] **Step 2: Run** them → FAIL.
- [ ] **Step 3: Implement** in `job.py`: after the `searching` phase, emit `searching` for every field of every group; run `_answer_group(fill_id, group, …)` per group through `run_groups(..., max_workers=settings.fill_max_parallel_calls)`, each with its own `SessionLocal()` and its own `knowledge_search(session, tenant_id)`; a shared `threading.Event` `stop` set on the first exception or on discard; `on_field` checks `stop` and `fill_exists` before publishing; the main thread waits for all futures, re-raises the first exception (then the existing `run_fill` error handling applies) and aggregates `types`, `usage`, `search_seconds`. Log per group then the total. Engine: `pool_size = fill_max_parallel_calls + 5`. Rename the setting and update `forms/service.py` to count groups with `call_groups` (fetch fields per form; `skip` empty).
- [ ] **Step 4: Run** `uv run pytest` → PASS; ruff, pyright clean.
- [ ] **Step 5: Commit** `feat(filling): model calls run in parallel, one session per group; estimate from parallel rounds`.

### Task 4: Recording script with groups, in parallel, per form

**Files:**
- Modify: `backend/scripts/record_llm.py`
- Modify: `backend/app/llm/fake_adapter.py` (`RecordingLLM`, only if not thread-safe)
- Test: `backend/tests/llm/test_fake_adapter.py`

**Interfaces:**
- Consumes: `call_groups`, `answer_section(group=...)`, `Settings.fill_max_parallel_calls`.
- Produces: `uv run python -m scripts.record_llm [--add-demo-documents] [--form annex-4]` (`--form` = a prefix of the slugged file name; default: every parsed form).

- [ ] **Step 1: Write the failing test** `test_recording_llm_records_concurrent_calls_to_their_own_files`: `RecordingLLM` over a fake that answers per key, two calls from two threads → two files, each with its key's answer and a `timing` block.
- [ ] **Step 2: Run** → FAIL if `RecordingLLM` is not thread-safe, else PASS (then keep the test as a guard).
- [ ] **Step 3: Implement** the script: groups via `call_groups` (one DB session per group, as in the job), run in the pool; print per group `[+t s] arrived: key` lines, `result.describe()`, the decided type and value of each field and the rejected reasons, then `Total: wall time · search · model cost` (sum of usage, wall-clock duration). `--form` filter.
- [ ] **Step 4: Run** `uv run pytest tests/llm -v` → PASS; `uv run python -m scripts.record_llm --help` shows `--form`.
- [ ] **Step 5: Commit** `feat(scripts): record model answers per group, in parallel, optionally for one form`.

### Task 5: Real Annex 4 recording, checked against the ground truth (paid, user checkpoints)

**Files:**
- Create: `backend/llm_recordings/annex-4-conditions-of-participation-and-company-self-declaration--*.json` (9 files)
- Modify (only for generic fixes): `backend/app/modules/filling/answer_engine.py` (`INSTRUCTIONS`), search parameters
- Modify: `backend/tests/modules/filling/test_recorded_answers.py`
- Modify: `backend/app/core/config.py` (`fill_seconds_per_call` after measuring)

- [ ] **Step 1: Run one attempt**: `make db` running, then `cd backend && uv run python -m scripts.record_llm --add-demo-documents --form annex-4` (first time; then without `--add-demo-documents`). Needs `OPENAI_API_KEY` in `backend/.env` (never read the file).
- [ ] **Step 2: Compare to `knowledge-base/GROUND_TRUTH.md`** (Annex 4 tables): factual values; conflict on the AHV address (Hardturmstrasse 120 first); `outdated` on the three per-claim amounts; `missing` for auxiliary staff, apprentices, VAT, UVG, both "services abroad" questions, both foreign-bidder fields; Yes/No `declaration` with the expected evidence (doc 10, 06, 07/08, 02, 11); no invented value, no declaration without verified proof.
- [ ] **Step 3: STOP — report to the user**: cost of the attempt (and running total), wall time, first field, the gaps table. **Wait for the user's go-ahead.** On their go-ahead, apply a generic simple fix (prompt or search) and go back to Step 1, or stop and list the remaining gaps for the known limits.
- [ ] **Step 4: Write the replay test** `test_the_recorded_annex_4_fill_flags_the_traps` (replays `llm_recordings/` like the Annex 7 test): asserts on the trap fields only, by key — `ahv_compensation_office_exact_address` type `conflict` with value containing "Hardturmstrasse 120"; `personal_injury` / `property_damage` / `financial_loss` type `outdated`; `have_you_paid_in_full_the_vat_or_sales_tax_due` absent or `missing`; the occupational-health declaration `declaration` with value `yes`; `uid` `auto` "CHE-123.456.789"; `ai_run.status == "done"` — adjusted to what the accepted recording actually gives (gaps accepted by the user are not asserted). If the hash embedder of the fast tests drops quotes the recording relies on, mark this test `slow` (real embedder) and say so in its docstring.
- [ ] **Step 5: Write** `test_the_recorded_annex_4_fill_keeps_fields_set_by_hand` (Review Focus 3): set two Table 7 declarations by hand, auto-fill → those two keep the user's values, the 16 others of Table 7 are answered as in the full replay, `done`.
- [ ] **Step 6: Set** `fill_seconds_per_call` to the measured slowest group, rounded up to 5 s; update the estimate test if it changes.
- [ ] **Step 7: Run** `uv run pytest` (and `uv run pytest -m slow` if Step 4 went slow) → PASS.
- [ ] **Step 8: Commit** `feat(llm): recorded Annex 4 answers` (recordings, test, any generic fix as its own commit before it).

### Task 6: e2e and documentation

**Files:**
- Modify: `frontend/e2e/main-scenario.spec.ts`
- Modify: `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `backend/CLAUDE.md`; propose the root `CLAUDE.md` update to the user (ask for validation before editing it)

- [ ] **Step 1: Change the e2e's Annex 4 part**: from *Tender*, `Auto-fill` on the Word card → *Setup* dialog → `Start`; in *Live fill*, wait for the final counters (`"N / 48 filled · E empty · D doubts"`, N/E/D taken from the accepted recording's replay test), a declaration answered `Yes` visible in the Word preview (`wordPreview.getByLabel("Do you comply with the applicable occupational health and safety regulations?")` has text `Yes`, if the recording answers it), then correct one field by hand and export the DOCX (existing download assertions kept). Drop the open-by-URL path and the "auto-fill comes with step 6c" comment.
- [ ] **Step 2: Run** `cd frontend && pnpm exec playwright test` → PASS.
- [ ] **Step 3: Run** `make test && make lint && make typecheck` at the repo root → all PASS.
- [ ] **Step 4: Update the docs**: `docs/PLAN.md` 6c section (what was built, measured time and cost of the Annex 4, known limits, decision log lines: groups ≤ 10, parallel pool 10, heading context, user approval between paid recordings), status line; `docs/ARCHITECTURE.md` (parallel job, groups, `field.context`); `backend/CLAUDE.md` (Annex 4 measure, `FORMPILOT_FILL_MAX_PARALLEL_CALLS`, `--form`). Show the user the proposed root `CLAUDE.md` changes (Word Auto-fill no longer stops with "No recorded answer") and edit only after approval.
- [ ] **Step 5: Commit** `test(e2e): Annex 4 auto-filled end to end` and `docs: step 6c`.
