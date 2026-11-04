# 5d — Auto-fill UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The user starts the automatic fill of a form from *Setup* and watches the PDF and the field list fill one field at a time, with a progress bar that always moves; a fill can be discarded to start over.

**Architecture:** The LLM facade gains an optional partial-output callback: the OpenAI adapter streams (Responses API) and parses partial JSON; `FakeLLM` replays the final JSON in chunks, spread over the recorded timing (or instantly). The answer engine publishes each field as soon as it is complete in the partial output; the job records and emits it at once (existing SSE). The front reads the SSE stream with `fetch` (no `EventSource` in Node/jsdom), applies each answer to the TanStack cache and computes the progress with a pure function.

**Tech Stack:** FastAPI, SQLAlchemy, OpenAI SDK (`responses.stream`), `pydantic_core.from_json(allow_partial=True)`; Next.js 16, TanStack Query, next-intl, shadcn/ui (`dropdown-menu`, `progress`), `eventsource-parser`, Vitest + MSW 3, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-04-5d-auto-fill-ui-design.md`

## Global Constraints

- **No "AI" in the interface** (user decision): "Auto-fill", "Filling the form…", "Filled automatically", "From your documents", "Not found in your documents". No ✦ / `SparklesIcon`. Applies to every `en.json` text and to every back message that reaches the user (`UNEXPECTED_ERROR`, 409/422/503 details, `INTERRUPTED`).
- All interface text in `frontend/src/shared/i18n/messages/en.json` (skill `frontend-i18n`); dates through `shared/utils/date.ts`; keyboard through `useHandleKeyDown`.
- Data layer: `[feature].api.ts` (HTTP only) / `[feature].queries.ts` (hooks), skill `frontend-data-layer`; no imports between features (the screen composes).
- Screen tests per skill `screen-tests` (Given/When/Then, user-event, MSW handlers in `shared/test/handlers.ts`, fixtures in `shared/test/fixtures/`).
- `FakeLLM` latency: setting `FORMPILOT_FAKE_LLM_LATENCY` = `recorded` (default, demo) | `none`; pytest and the e2e run with `none`; no real sleep in any test.
- No re-run on a started form: only `not_started` forms can be auto-filled; *Discard answers* deletes everything (user values included) and sets the form back to *Not started*.
- Out of scope (later steps): `Source` tab, filters/grouping, conflict/outdated action cards, parallel sections, export blocking.
- Never read `backend/.env`. After each back API change: `make gen-api`. After each model change: `make db-schema`.
- Commits: small, one per task at least, ending with the attribution lines of the session.

## Review Focus

1. **Discard while the job is writing** — the job's next insert hits a deleted `form_fill` (FK violation) or a new fill started meanwhile: the old job must stop silently, never write into the new fill, never log an error event. Test in Task 4.
2. **A field the user is typing in receives its answer** — the input keeps what is typed (no remount losing text) and the user's save wins. Test in Task 10.
3. **Page reloaded during the fill** — the stream replays from the start; the screen shows the same phase, answered fields and progress, without duplicating counts. Test in Task 10.
4. **Partial JSON cut inside a string, a key or between two items** — no field published twice, no field published before it is complete, last field published at the end. Test in Task 2.
5. **Model echoes a label instead of a key, or skips a field** — matched by label as in 5c, skipped field ends `missing` at the end of the section, never during. Test in Task 2.

---

### Task 1: Streaming in the LLM facade (OpenAI + FakeLLM + recordings with timing)

**Files:**
- Modify: `backend/app/llm/facade.py`, `backend/app/llm/openai_adapter.py`, `backend/app/llm/fake_adapter.py`, `backend/app/core/config.py`, `backend/tests/conftest.py`, `frontend/playwright.config.ts` (env `FORMPILOT_FAKE_LLM_LATENCY: "none"`)
- Test: `backend/tests/llm/test_fake_adapter.py`

**Interfaces:**
- Produces:
  - `OnPartial = Callable[[dict[str, Any]], None]` in `facade.py`.
  - `LLM.generate_structured[T](self, request: LLMRequest[T], on_partial: OnPartial | None = None) -> LLMResult[T]` — `on_partial` receives the partial output parsed so far (a JSON object, possibly incomplete), called several times, in order, before returning.
  - `FakeLLM(answers, *, latency: Literal["recorded", "none"] = "none", sleep: Callable[[float], None] = time.sleep)`; `FakeLLM.from_dir(directory, *, latency=...)`.
  - Recording file: the answer JSON plus a top-level `"timing": {"first_output_seconds": float, "total_seconds": float}` key (popped before validation; files without it replay with no delay).
  - Setting `fake_llm_latency: Literal["recorded", "none"] = "recorded"`; `get_llm()` passes it.

- [ ] **Step 1: Write the failing tests** in `test_fake_adapter.py`:
  - `test_replay_streams_partial_outputs_in_order`: answers `{"k": {"fields": [{"a": 1}, {"a": 2}, {"a": 3}]}}`; collected partials are non-empty, each one's `fields` length is ≥ the previous one's, the last partial equals the full output.
  - `test_replay_without_latency_never_sleeps`: `sleep` spy never called (latency `none`).
  - `test_replay_with_recorded_latency_spreads_the_recorded_time`: recording with `timing {first_output_seconds: 4.0, total_seconds: 10.0}`, latency `recorded`, `sleep` spy: first sleep == 4.0, total of sleeps == pytest.approx(10.0).
  - `test_timing_is_not_part_of_the_output`: output validates against a strict (`extra="forbid"`) schema.
  - `test_recording_writes_the_timing`: `RecordingLLM` over a stub LLM that calls `on_partial` then returns; file has `timing.first_output_seconds` ≤ `timing.total_seconds`, and the stub's partials reach the caller's `on_partial`.

- [ ] **Step 2: Run** `cd backend && uv run pytest tests/llm -v` — Expected: FAIL (unexpected keyword `on_partial` / `latency`).

- [ ] **Step 3: Implement.**
  - `FakeLLM`: serialize the output (`json.dumps`), cut it into 20 chunks of equal length; for chunk i, sleep (`recorded` only: first sleep `first_output_seconds`, then `(total - first) / 20` per chunk) and call `on_partial(pydantic_core.from_json(prefix, allow_partial=True))`.
  - `OpenAILLM`: `with self._client.responses.stream(model=…, instructions=…, input=…, text_format=request.schema, reasoning=…, store=False) as stream:` accumulate `event.delta` of `response.output_text.delta` events, call `on_partial` with `from_json(text, allow_partial=True)` (skip when parsing gives nothing); then `stream.get_final_response()` → `output_parsed` + usage as today. `openai.APIError` → `LLMError` as today.
  - `RecordingLLM`: measures the time of the first `on_partial` call and the total; writes `timing` with the answer.
  - `tests/conftest.py`: set `FORMPILOT_FAKE_LLM_LATENCY=none` with the other test env settings.

- [ ] **Step 4: Run** `uv run pytest tests/llm -v && uv run pytest && uv run pyright` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(llm): stream partial outputs; FakeLLM replays the recorded timing`

### Task 2: Answer engine publishes each field as soon as it is complete

**Files:**
- Modify: `backend/app/modules/filling/answer_engine.py`
- Test: `backend/tests/modules/filling/test_streaming.py` (new, pure, no DB)

**Interfaces:**
- Consumes: `OnPartial`, `generate_structured(request, on_partial=…)` (Task 1).
- Produces:
  - `complete_items(partial: dict[str, Any], key: str) -> list[dict[str, Any]]` — the items of `partial[key]` known to be complete: all but the last (pure).
  - `OnField = Callable[[int, ValidatedField], None]`.
  - `answer_section(..., on_field: OnField | None = None) -> SectionResult` — `on_field` called exactly once per field of `fields`, in the order the model completes them, then for the fields never answered (not found) at the end; `SectionResult.evidence` unchanged.

- [ ] **Step 1: Write the failing tests:**
  - `complete_items`: `{}` → `[]`; `{"fields": [{…}]}` → `[]`; two items → first only; partial cut inside a string of item 2 → item 1 only.
  - `test_fields_are_published_while_the_model_writes`: `FakeLLM` scripted for a 3-field section; `on_field` records `(field_id, len(partials_seen_so_far))`; first field is published before the last partial.
  - `test_each_field_is_published_once` (chunks cutting inside keys and strings: use an output whose JSON length is not a multiple of 20).
  - `test_a_field_answered_by_its_label_is_matched` (model echoes the label).
  - `test_a_skipped_field_is_published_not_found_at_the_end`: model answers fields 1 and 3 only; field 2 published last, with no candidates.
  - `test_published_evidence_equals_the_final_evidence`: for each field, `on_field` value == `SectionResult.evidence[field_id]`.

- [ ] **Step 2: Run** `uv run pytest tests/modules/filling/test_streaming.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement.** In `answer_section`, an `on_partial` closure: for each new item of `complete_items(partial, "fields")`, `LLMFieldAnswer.model_validate(item)` (skip an invalid item), match by key then label as today, `validate_field` with the same passages, `on_field` if that field was not published yet. After the call: publish the remaining items of the final output, then the fields still unpublished (`validate_field(kind, None, passages)`).

- [ ] **Step 4: Run** `uv run pytest tests/modules/filling -v` — Expected: PASS (5c tests unchanged).

- [ ] **Step 5: Commit** `feat(filling): publish each field as soon as the model completes it`

### Task 3: Job records and emits each field as it arrives

**Files:**
- Modify: `backend/app/modules/filling/job.py`
- Test: `backend/tests/modules/filling/test_ai_fill.py`

**Interfaces:**
- Consumes: `answer_section(..., on_field=…)` (Task 2).
- Produces: unchanged event contract (`field` `answered` with `answer` + `counts`), now emitted during the section's call.

- [ ] **Step 1: Write the failing test** `test_answers_are_emitted_while_the_section_is_being_answered`: a `FakeLLM` subclass whose `on_partial` hook, after the first partial that completes field 1, reads the `fill_event` table in another session: at least one `field` `answered` event exists before `generate_structured` returns.
- [ ] **Step 2: Run** — Expected: FAIL (all answered events written after the call).
- [ ] **Step 3: Implement.** Move the per-field `decide` / `record_ai_answer` / commit / `answered` event block into the `on_field` callback passed to `answer_section`. Reword `UNEXPECTED_ERROR` without "AI": "Something went wrong while filling this form." (and `INTERRUPTED` in `service.py`, the 409/422 details: "This form is already being filled.", "This form cannot be filled automatically yet: its format is not read.").
- [ ] **Step 4: Run** `uv run pytest tests/modules/filling -v` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(filling): emit each answer as soon as it is validated`

### Task 4: Discard a fill (`DELETE /forms/{id}/fill`), also during a run

**Files:**
- Modify: `backend/app/modules/filling/service.py`, `backend/app/modules/filling/router.py`, `backend/app/modules/filling/job.py`
- Test: `backend/tests/modules/filling/test_discard.py` (new)

**Interfaces:**
- Produces: `DELETE /forms/{form_id}/fill` → 204 (also when nothing was started), 404 unknown form. `service.discard_fill(session, tenant_id, form_id) -> None` deletes the tenant's `form_fill` row (answers and events cascade) → status `not_started`. `service.fill_exists(session, fill_id) -> bool`.

- [ ] **Step 1: Write the failing tests:**
  - `test_discard_deletes_every_answer_the_users_included`: user value + AI fill done → DELETE → `GET /answers` has no answers, `ai_run` null; tender form status `not_started`.
  - `test_a_discarded_form_can_be_auto_filled_again`: DELETE then `POST /fill` → 202.
  - `test_discard_of_an_unknown_form_is_404`; `test_discard_of_another_tenants_fill_leaves_it` (helpers of `test_tenancy.py`).
  - `test_discard_during_a_run_stops_the_job_silently`: `FakeLLM` whose `on_partial` hook calls `discard_fill` in another session after field 1; then `run_fill` returns without raising; no `form_fill` for the tenant; no error logged at ERROR level (`caplog`).
  - `test_discard_then_restart_during_the_old_run_never_writes_into_the_new_fill`: hook discards and starts a new fill (new id); after `run_fill(old_id)` the new fill has no answers from the old job.
  - `test_the_event_stream_of_a_discarded_run_ends`: `GET /fill/events` after a discard returns (no hang).
- [ ] **Step 2: Run** — Expected: FAIL (405 / job raises).
- [ ] **Step 3: Implement.** Router `DELETE "/fill"`, `status_code=204`. Job: `_Discarded` exception raised in `on_field` and between phases when `not service.fill_exists(session, fill_id)`; `run_fill` catches it (and an `IntegrityError` when the fill is gone) → rollback and return, no event. `events_after` already ends when status is `None`.
- [ ] **Step 4: Run** `uv run pytest -v` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(filling): discard a form's fill, also while it is running`

### Task 5: What *Setup* and the cards need from the API

**Files:**
- Modify: `backend/app/modules/forms/schemas.py`, `backend/app/modules/forms/service.py`, `backend/app/modules/tenders/schemas.py`, `backend/app/modules/tenders/service.py`, `backend/app/modules/filling/service.py` (`fill_statuses`), `backend/app/core/config.py`
- Test: `backend/tests/modules/test_tenders.py`, `backend/tests/modules/forms/test_api.py`
- Then: `make gen-api` (frontend `schema.gen.ts`)

**Interfaces:**
- Produces:
  - `FormInfo.estimated_fill_seconds: int | None` = number of distinct sections × `settings.fill_seconds_per_section` (default `25`); null when `field_counts` is null. On `FormSummary` and `FormDetail`.
  - `FormSummary.filling: bool` — the tenant's run is `running`.
- [ ] **Step 1: Write the failing tests:** Annex 7 has `estimated_fill_seconds == 25` (1 section), Annex 4 `None`; `filling` is false, true after `POST /fill` with a `FakeLLM` that blocks (hook) — or set `ai_status` directly in the DB, simpler.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** (sections counted from the form's fields).
- [ ] **Step 4: Run** `uv run pytest && uv run pyright && make gen-api && cd frontend && pnpm typecheck` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(api): estimated fill duration and running flag on forms`

### Task 6: Record Annex 7 again with its timing

**Files:**
- Modify: `backend/llm_recordings/annex-7-self-declaration-art29c-ukraine-ordinance--page-1.json`, `backend/tests/modules/filling/test_recorded_answers.py` (only if the new answer differs and still matches `GROUND_TRUTH.md`)

- [ ] **Step 1: Run** `make db` then `cd backend && FORMPILOT_LLM_PROVIDER=openai uv run python -m scripts.record_llm --add-demo-documents` (the app reads the key from `backend/.env`; never open it). Expected: cost ~$0.005 and timing printed; file has a `timing` block.
- [ ] **Step 2: Run** `uv run pytest tests/modules/filling/test_recorded_answers.py -v` — Expected: PASS. If an answer changed, compare with `knowledge-base/GROUND_TRUTH.md`; a change that breaks the ground truth is reported to the user, not "fixed" in the test.
- [ ] **Fallback** (call fails): keep the current answer, add `"timing": {"first_output_seconds": 6.0, "total_seconds": 23.0}` by hand, and tell the user.
- [ ] **Step 3: Commit** `chore(llm): record Annex 7 with streaming timing`

### Task 7: Front data layer — start, discard, follow the fill

**Files:**
- Modify: `frontend/src/features/fill-session/fill-session.api.ts`, `fill-session.queries.ts`, `index.ts`
- Create: `frontend/src/features/fill-session/fill-events.ts` (event types + reducer, pure), `fill-events.test.ts`
- Modify: `frontend/src/shared/test/handlers.ts` (handlers `startFill`, `discardFill`, `fillEvents`), `frontend/package.json` (`eventsource-parser`)

**Interfaces:**
- Produces:
  - `type FillEvent = { id: number } & ({ type: "phase"; phase: FillPhase; …data } | { type: "field"; field_id: number; state: "searching" } | { type: "field"; field_id: number; state: "answered"; answer: Answer; counts: FillState["counts"] } | { type: "done"; filled: number; fillable: number; doubts: number; seconds: number } | { type: "error"; message: string })`; `FillPhase = "reading_form" | "detecting_fields" | "searching" | "cross_checking" | "preparing_review"`.
  - `type FillRun = { phase: FillPhase | null; toAnswer: number | null; searching: ReadonlySet<number>; answered: ReadonlySet<number>; lastProgressAt: number | null; outcome: null | { kind: "done"; filled: number; fillable: number; seconds: number } | { kind: "error"; message: string } }`; `initialRun`; `reduceRun(run: FillRun, event: FillEvent, at: number): FillRun` (pure).
  - `fillApi.startFill(formId)`, `fillApi.discardFill(formId)`, `fillApi.streamEvents(formId, { signal, onEvent: (event: FillEvent) => void }): Promise<void>` (fetch `GET /forms/{id}/fill/events`, `eventsource-parser`, resolves when the stream ends).
  - `useStartFill(formId)` (mutation; on success invalidates tender and answers), `useDiscardFill(formId)` (mutation; on success removes the form's queries and invalidates the tender).
  - `useFillRun(formId, { follow: boolean }): FillRun` — while `follow`, streams the events, reduces them, writes each `answered` answer + counts into `fillKeys.answers` (`setQueryData`, the answer replacing the previous one for that field, unless the cached one is `resolved_by: "user"`), and on `done`/`error` invalidates the answers and the tender. Aborts on unmount.
  - Test handler: `handlers.fillEvents(formId)` → `{ handler, send(event: FillEvent), close() }` (MSW response over a `ReadableStream` written by `send`).
- [ ] **Step 1: Write the failing tests** (`fill-events.test.ts`): `reduceRun` — phase updates `phase`; `detecting_fields` sets `toAnswer`; `searching` adds to `searching`; `answered` moves the field from `searching` to `answered` and sets `lastProgressAt`; replaying the same events twice from `initialRun` gives the same run (reload); `done` / `error` set the outcome.
- [ ] **Step 2: Run** `cd frontend && pnpm test fill-events` — Expected: FAIL.
- [ ] **Step 3: Implement** (`pnpm add eventsource-parser`).
- [ ] **Step 4: Run** `pnpm test && pnpm typecheck && pnpm lint` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(front): start, discard and follow an automatic fill`

### Task 8: Progress, as a pure function

**Files:**
- Create: `frontend/src/features/fill-session/progress.ts`, `progress.test.ts`

**Interfaces:**
- Produces: `fillProgress(run: FillRun, { now: number; startedAt: number; estimatedSeconds: number }): number` in [0, 1].
- [ ] **Step 1: Write the failing tests** (values pinned by the spec §4.4):
  - before `searching`: ≤ 0.05; `outcome.kind === "done"`: 1; `cross_checking` / `preparing_review`: between 0.95 and 0.99.
  - during `searching` with k of n answered: ≥ `0.05 + 0.9 * k / n` and < `0.05 + 0.9 * (k + 1) / n`.
  - time creep: with 0 answered, progress at `now = startedAt + 10 s` > progress at `startedAt + 2 s` (estimated 25 s), and stays < the next milestone even at `startedAt + 600 s`.
  - never decreases: for a sequence of (run, now) in time order, values are non-decreasing (an answer arriving right after a long creep does not pull it back: the creep fraction restarts from the new milestone).
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** — creep toward the next milestone with `1 - exp(-t / τ)`, τ = `estimatedSeconds / (n + 1)` per step, capped at 90 % of the gap. **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(front): fill progress that always moves and never goes back`

### Task 9: Tender — *Auto-fill*, *Setup*, *Discard answers*

**Files:**
- Modify: `frontend/src/features/tender/FormList.tsx`, `frontend/src/screens/tender/TenderScreen.tsx`, `TenderScreen.test.tsx`, `en.json`, `shared/test/fixtures/tender.ts`
- Create: `frontend/src/features/fill-session/SetupDialog.tsx`, `frontend/src/features/fill-session/DiscardFillDialog.tsx`; `pnpm dlx shadcn@latest add dropdown-menu`

**Interfaces:**
- Consumes: `useStartFill`, `useDiscardFill` (Task 7); `FormSummary.estimated_fill_seconds`, `filling` (Task 5); documents count from `useKnowledge` (passed by `TenderScreen`).
- Produces: `<SetupDialog form={FormSummary} documentCount={number} onStarted={() => void} />` (its own trigger button "Auto-fill"); `<DiscardFillDialog formId formTitle open onOpenChange onDiscarded />`. `FormList` takes a `renderAction` / slot from the screen so `tender` does not import `fill-session` (_or_ the action component lives in the screen — implementer's choice within module rules).
- Copy (exact): button "Auto-fill"; dialog title "Auto-fill {formTitle}"; sources "Company knowledge · {count, plural, one {# document} other {# documents}}" and "Tender details"; empty knowledge "Your company knowledge is empty: only the tender details can be used." + link "Add documents"; duration "Takes about {seconds} seconds"; buttons "Cancel" / "Start"; 503 "Auto-fill is not available right now." + back detail; menu "More actions" → "Discard answers"; confirm "Discard all answers to {formTitle}?" / "Every value is deleted, including the ones you entered. This can't be undone." / "Cancel" / "Discard"; failure "We couldn't discard the answers. Try again."
- [ ] **Step 1: Write the failing screen tests:** not started → "Auto-fill" opens *Setup* with file name, counts, "Company knowledge · 11 documents", "Takes about 25 seconds"; "Start" → `POST /fill` then navigation to the fill route (router mock as in existing tests); 503 → message in the dialog, still open; 409 → navigates anyway; empty knowledge → warning + link; started form → "Continue review" + "More actions" → "Discard answers" → confirm → `DELETE` sent, card back to "Not started" + "Auto-fill"; cancel → nothing sent; failure → error shown; no element with text matching `/\bAI\b/` on the screen.
- [ ] **Step 2: Run** `pnpm test TenderScreen` — FAIL. **Step 3: Implement** (rename `fillWithAi` → `autoFill`, drop `SparklesIcon`). **Step 4: Run** `pnpm test && pnpm lint && pnpm typecheck` — PASS.
- [ ] **Step 5: Commit** `feat(tender): auto-fill setup and discard answers`

### Task 10: Live fill follows the fill (header, progress, list and PDF)

**Files:**
- Modify: `frontend/src/screens/live-fill/LiveFillScreen.tsx`, `LiveFillScreen.test.tsx`, `frontend/src/features/review-queue/FieldList.tsx`, `frontend/src/features/document-preview/DocumentPreview.tsx`, `frontend/src/features/form-export/ExportDialog.tsx` (disabled + "Filling…"), `en.json`, `shared/test/fixtures/annex7.ts`
- Create: `frontend/src/features/fill-session/FillProgress.tsx`; `pnpm dlx shadcn@latest add progress`

**Interfaces:**
- Consumes: `useFillRun`, `fillProgress`, `FillRun` (Tasks 7–8); `FormDetail.estimated_fill_seconds`; `fill.ai_run`.
- Produces: `QueueField` gains `state: "pending" | "searching" | "answered"`; `ZoneTone = "auto" | "toCheck" | "empty" | "entered" | "signature" | "searching"` — mapping: signature → `signature`; searching → `searching`; no value → `empty`; `resolved_by: "user"` → `entered`; `conflict` / `outdated` / `manual` → `toCheck`; `auto` / `declaration` → `auto`; `<FillProgress run estimatedSeconds startedAt />` (`role="progressbar"`, accessible name "Fill progress", re-renders every 250 ms while running).
- Copy (exact): "Filling the form…"; phases "Reading the form" · "Detecting fields" · "Searching your documents" · "Checking sources" · "Preparing your review"; "{answered} / {total}"; field "Searching your documents…"; end "{filled} of {fillable} fields filled in {seconds} seconds"; error banner "Auto-fill stopped: {message}"; export button "Filling…"; top-bar counts "{filled} / {fillable} filled · {empty} empty · {doubts} doubts"; legend "Filled automatically" · "To check" · "Empty" · "Entered by you" · "Sign by hand".
- [ ] **Step 1: Write the failing screen tests** (stream driven with `handlers.fillEvents(2).send(...)`):
  - running fill: header "Filling the form…" + phase; progress bar present; Export button disabled "Filling…".
  - `searching` events → fields show "Searching your documents…"; one `answered` event → that field shows its value in the list and on its PDF zone, the others still searching; counts in the top bar updated.
  - `done` → "8 of 9 fields filled in 23 seconds", Export enabled, first open field selected (`aria-current`).
  - `error` → "Auto-fill stopped: …", answers already received still shown.
  - typing in a field while its `answered` event arrives keeps the typed text in the input; leaving the field saves the typed text (PATCH body).
  - reload during the run: the handler replays the first events then stays open → same answered fields and phase shown, counts not doubled.
  - not running (`ai_run` null) → no stream request made (handler records none).
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** `follow = ai_run?.status === "running"` (also right after navigation from *Setup*: the answers query is invalidated by `useStartFill`). **Step 4: Run** `pnpm test && pnpm lint && pnpm typecheck` — PASS.
- [ ] **Step 5: Commit** `feat(live-fill): watch the form fill itself field by field`

### Task 11: Field card — status and source; discard from Live fill

**Files:**
- Modify: `frontend/src/features/review-queue/FieldList.tsx` (+ `FieldStatus.tsx`, `FieldSources.tsx` if it grows), `LiveFillScreen.tsx`, `LiveFillScreen.test.tsx`, `en.json`, fixtures

**Interfaces:**
- Consumes: `Answer` (`type`, `candidates[].citations[] {quote, document_name, document_id, page}`, `user_only_reason`, `resolved_by`); `DiscardFillDialog` (Task 9); company name from the knowledge query or a constant of the fixtures — the screen passes it.
- Produces: `QueueField` gains `type: Answer["type"]`, `resolvedBy`, `candidates`, `userOnlyReason`.
- Copy (exact): auto "Filled automatically"; declaration "Filled automatically · you declare this on behalf of {company}"; missing "Not found in the passages searched in your {count, plural, one {# document} other {# documents}}"; manual "Only you can fill this" + reason; conflict "{count} sources disagree"; outdated "Source expired on {date}" (date from the selected candidate's `valid_until`, Swiss format); user "Entered by you · {time}" (existing); source "{document}, page {page}" + quote in quotes; tender details (`document_id` null) "Tender details"; top-bar menu "More actions" → "Discard answers".
- [ ] **Step 1: Write the failing screen tests:** one case per type (auto with source document + page + quote; declaration; missing with document count; manual with reason and suggested value in the input; conflict lists all sources; outdated shows the date `dd.mm.yyyy`; user value keeps the earlier source visible); source of the selected field expanded, others collapsed; Tender details source; discard from the top bar → confirm → `DELETE` → navigates to the tender; discard during a running fill works the same.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** `pnpm test && pnpm lint && pnpm typecheck` — PASS.
- [ ] **Step 5: Commit** `feat(live-fill): status and source of each answer; discard answers`

### Task 12: e2e — the main scenario with auto-fill

**Files:**
- Modify: `frontend/e2e/main-scenario.spec.ts`

- [ ] **Step 1: Extend the scenario** (rename the test "I auto-fill Annex 7 from my documents, correct a field and download it in its original PDF layout"): after adding the 11 demo documents → *Tender* → "Auto-fill" on Annex 7 → *Setup* shows "11 documents" → "Start" → *Live fill*; wait for "9 of 9 fields filled" (exact count from the recording, read it from Task 6's result); "Business address" shows "Pfingstweidstrasse 31, 8005 Zurich" with source document name + page; correct one field by hand; export → downloaded PDF contains the corrected value and an auto value (existing PDF text check). Then back → "More actions" → "Discard answers" → card "Not started".
- [ ] **Step 2: Run** `make e2e` (or `cd frontend && pnpm e2e`) — Expected: PASS.
- [ ] **Step 3: Commit** `test(e2e): auto-fill Annex 7 end to end`

### Task 13: Docs and manual demo check

**Files:**
- Modify: `docs/USER_FLOW.md` (vocabulary rule, renamed labels, no re-run + discard), `docs/PLAN.md` (5d detailed like 5a–5c, journal lines: streaming, simulated latency, product vocabulary, Source tab at step 6, discard instead of re-run), `docs/ARCHITECTURE.md` (facade streaming, recordings timing, SSE read by fetch), `backend/CLAUDE.md` (`FORMPILOT_FAKE_LLM_LATENCY`), `CLAUDE.md` (product decisions — **ask the user to validate the diff before committing**)

- [ ] **Step 1: Manual check** with `make dev` (fake LLM, latency `recorded`), skill `next-dev-loop`: from an empty knowledge base, add the demo documents, Auto-fill Annex 7: fields appear one by one over ~20 s, bar never still, PDF updated; discard; screenshot for the user.
- [ ] **Step 2: Update the docs**, show the `CLAUDE.md` diff to the user and wait for validation.
- [ ] **Step 3: Run** `make lint && make typecheck && make test` — Expected: PASS.
- [ ] **Step 4: Commit** `docs(plan): step 5d`
