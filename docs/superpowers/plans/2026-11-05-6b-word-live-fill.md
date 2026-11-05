# 6b — Annex 4 in Live fill (Word preview, manual fill, export) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The user fills the Annex 4 (Word) by hand in Live fill, sees each value on a rendered Word preview where the export writes it, and downloads the filled DOCX.

**Architecture:** Back: `parse_docx` registered at seed, Word page sizes from `sectPr` × `docProps/app.xml` pages, Yes/No values validated. Front: `PreviewZone` gets a format-specific `place`; a `WordDocument` renders the DOCX with `docx-preview` and decorates it imperatively through two pure-DOM functions (`findParagraph`, `writePreviewValue`) that apply the 6a `DocxLocator` (character offsets) to the rendered HTML; Yes/No fields get Yes/No buttons; Auto-fill is disabled for Word forms until 6c.

**Tech Stack:** FastAPI/pytest (back); Next 16, React 19, TanStack Query, next-intl, `docx-preview` 0.4 (already a dependency, runs under jsdom), Vitest + MSW, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-05-6b-word-live-fill-design.md`

## Global Constraints

- No "AI" in the interface; all text through next-intl (`shared/i18n/messages/en.json`), skill `frontend-i18n`.
- Front structure: `app → screens → features → shared`, no imports between features (ESLint boundaries); data access per skill `frontend-data-layer`; component style per `frontend-code-style`; screen tests per `screen-tests`.
- Yes/No values stored as `yes` / `no`; displayed and exported `Yes` / `No`.
- Auto-fill disabled for `file_format === "docx"` only, with a comment marking it temporary (removed in 6c).
- Back checks: `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run pyright`. Front: `pnpm typecheck && pnpm lint && pnpm test`; e2e `pnpm e2e`.
- Front types regenerated from the code's OpenAPI if a schema changes (`openapi-typescript` on `app.openapi()` dumped in-process — the :8000 API is the user's dev server).

## Review Focus

1. Typing a draft that is then cleared: the preview must remove the inserted value and show the dots / empty paragraph again → `writePreviewValue` idempotence + empty-value test (Task 2).
2. Two fields in one rendered paragraph (Place and date + signature): inserting the first value must not shift the second zone → test on paragraph 33 of Annex 4 (Task 2).
3. Re-render of the Word document (zones change on every keystroke): never re-run `renderAsync`, only re-decorate → screen test asserts the document is rendered once (Task 3).
4. A Yes/No answer stored as `Yes` or `YES` by an older client: shown as selected → FieldList test with `"Yes"` (Task 4); the back normalises to lower case (Task 1).
5. Document fails to load (404 / corrupt): message `documentLoadError`, the field list still works → screen test (Task 3).

---

### Task 1: Back — Word forms parsed at seed, page sizes, Yes/No values

**Files:**
- Modify: `backend/app/modules/forms/parsing/docx_parser.py` (pages), `backend/app/modules/forms/service.py` (`PARSERS`), `backend/app/modules/filling/service.py` (`set_answer`)
- Test: `backend/tests/modules/forms/test_docx_parser.py`, `backend/tests/modules/forms/test_api.py`, `backend/tests/modules/filling/test_api.py`, `backend/tests/modules/export/test_api.py` (drop the `word_client` monkeypatch, now the default)

**Interfaces:**
- Produces: `parse_docx(...).pages` = `[PageSize(width, height)] * n` (points); `PATCH /forms/{id}/fields/{fieldId}` on a `yes_no` field accepts `yes` / `no` in any case (stored lower case) or blank, else 422 `"Answer Yes or No."`.

- [ ] **Step 1: Failing tests**
  - `test_annex_4_pages`: `[(round(p.width), round(p.height)) for p in annex_4.pages] == [(595, 842)] * 3`.
  - `test_pages_without_app_properties_count_word_breaks`: a synthetic document (python-docx; remove `docProps/app.xml` from the zip in the test, add two paragraphs with a `w:lastRenderedPageBreak` run child) → 3 pages of the section size.
  - forms `test_api.py`: replace `test_a_word_form_has_no_fields_yet` with `test_a_word_form_is_parsed_at_seed`: Annex 4 card `field_counts == {"fields": 49, "yes_no": 17, "signatures": 1}`, detail has 49 fields, `locator["format"] == "docx"`, 3 pages; update `test_tender_cards_show_what_was_detected_in_each_form`.
  - filling `test_api.py`: `test_a_yes_no_field_takes_yes_or_no` (`"Yes"` → stored `"yes"`; `"maybe"` → 422 with the message; `""` → empty).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Page size: first `w:sectPr/w:pgSz` (`w:w`, `w:h` twips / 20), A4 (595.3 × 841.9) if absent. Page count: `docProps/app.xml` `<Pages>` (read with `zipfile` + regex or ElementTree), else `count(w:lastRenderedPageBreak in distinct paragraphs) + 1`. Register `FileFormat.DOCX: parse_docx`. Yes/No check in `filling_service.set_answer` (raises `RuleViolationError`).
- [ ] **Step 4: Run** back checks → PASS. Check `tests/modules/tenders`, e2e expectations untouched by the counts (the e2e only checks "DOCX").
- [ ] **Step 5: Commit** `feat(forms): Word forms parsed at seed, page sizes, Yes/No answers`.

### Task 2: Front — locator → rendered Word DOM (pure functions)

**Files:**
- Create: `frontend/src/features/document-preview/docx-locator.ts`, `frontend/src/features/document-preview/docx-locator.test.ts`
- Test reads the real file `../forms/Annex_4_…docx` and renders it with the real `docx-preview` (`renderAsync(blob, container, undefined, { inWrapper: false, ignoreLastRenderedPageBreak: false })`).

**Interfaces:**
- Produces:
  ```ts
  export type DocxLocator = Schema<"DocxLocator">;
  /** The paragraph the locator points at in a docx-preview rendering (null when absent). */
  export function findParagraph(root: Element, locator: DocxLocator): HTMLElement | null;
  /** Show `value` where the export writes it (idempotent; null/blank removes it). Returns the
   *  element to highlight (the paragraph holding the value, or the label paragraph). */
  export function writePreviewValue(paragraph: HTMLElement, locator: DocxLocator, value: string | null): HTMLElement;
  ```
  Body = `root.querySelectorAll("section.docx > article")` children in order; tables/paragraphs indexed separately (spec §3). Inserted nodes carry `data-preview-value`; hidden leader chars are wrapped in `<span data-preview-leader hidden>`.

- [ ] **Step 1: Failing tests** (fixture keys from the 6a Annex 4 schema, locators copied into the test):
  - `findParagraph` returns the expected text for: `exact_company_name` (empty cell → `""`), `legal_form` (`"Legal form: \t"` rendered → starts with `"Legal form:"`), `main_activity`, `with_higher_professional_training` (empty paragraph), `remarks`, `place_and_date` (body paragraph 33 → starts with `"Place and date:"`).
  - `writePreviewValue`: `place_and_date` "Zurich, 05.11.2026" → paragraph text starts with `"Place and date: Zurich, 05.11.2026"` and still ends with `"signature(s):"`; then `null` → original text back; called twice with the same value → value present once.
  - leader (`tender_no_type_of_work`): text becomes `"Tender (No. ZH-1, type of work)"`; blank → dots back.
  - `new_paragraph` (`with_professional_training`): a new `<p>` after the label with `"9"`; the label paragraph unchanged; clearing removes it.
  - Yes/No (`yes`) → `"Yes"`; a value with a line break → one line.
- [ ] **Step 2: Run** `pnpm vitest run src/features/document-preview/docx-locator.test.ts` → FAIL.
- [ ] **Step 3: Implement** (offsets counted on `textContent` of the paragraph's text nodes, a rendered tab being one character; insertion splits a text node; same leading-space rule as the exporter).
- [ ] **Step 4: Run** → PASS; `pnpm typecheck && pnpm lint`.
- [ ] **Step 5: Commit** `feat(preview): locate and write Word fields in the rendered document`.

### Task 3: Front — Word preview in Live fill

**Files:**
- Create: `frontend/src/features/document-preview/WordDocument.tsx`, `frontend/src/shared/test/fixtures/annex4.ts`
- Modify: `frontend/src/features/document-preview/DocumentPreview.tsx` (`PreviewZone.place`, dispatch by format), `index.ts`, `frontend/src/screens/live-fill/LiveFillScreen.tsx` (zones for both formats, `fileFormat` passed), `frontend/src/shared/test/handlers.ts` (serve the real Annex 4 file for `/forms/{id}/file` when asked), `en.json`
- Test: `frontend/src/screens/live-fill/LiveFillScreen.test.tsx` (new `describe("a Word form")`)

**Interfaces:**
- Consumes: Task 2 functions.
- Produces: `PreviewZone = { id; label; value; tone; place: { format: "pdf"; page; box; fontSize; placeholders } | { format: "docx"; locator: DocxLocator } }`; `DocumentPreview({ fileUrl, fileFormat, pages, zones, selectedId, onSelect })`.
- Fixture `annex4.ts`: the 49 fields with ids, keys, labels, kinds, sections and locators, written from the back parser's output (dump once with a script, kept as data) plus `annex4FormDetail()` like `annex7`.

- [ ] **Step 1: Failing screen tests:**
  - `I type a value and see it on the Word form`: type into "Exact company name" → the zone `[data-field-id]` of that field contains "Alpenlogic AG" before leaving the input; after Tab, saved (MSW PATCH called, "Saved").
  - `I click a zone on the Word form to select its field`: click the "Insurance company" zone → its input is focused.
  - `the Word form is rendered once while I type` (Review Focus 3): spy on `docx-preview`'s `renderAsync` (vi.spyOn on the module namespace) → called once after typing 5 characters.
  - `the field list still works when the Word document cannot be loaded` (Review Focus 5): file handler 404 → "We couldn't display this document…" shown, inputs present.
  - `I export the Word form`: "Export DOCX" → dialog "Download DOCX" link to `/forms/{id}/export/file`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `WordDocument`: fetch the file once (TanStack Query in `document-preview`'s own api/queries per `frontend-data-layer`, or `fetch` in an effect keyed by `fileUrl`), `renderAsync` once per file into a ref'd container; a layout effect on `zones`/`selectedId` re-applies `writePreviewValue`, tone classes (same `TONES` as PDF), `data-field-id`, `aria-label`, click handlers (event delegation on the container), `scrollIntoView({ block: "center" })` on selection change. Skeleton while loading, `documentLoadError` on failure. Remove the PDF-only `flatMap` filter in `LiveFillScreen`.
- [ ] **Step 4: Run** front checks → PASS (Annex 7 screen tests unchanged).
- [ ] **Step 5: Commit** `feat(live-fill): Word forms previewed and filled by hand`.

### Task 4: Front — Yes/No answers with buttons

**Files:**
- Modify: `frontend/src/features/review-queue/FieldList.tsx` (`QueueField.kind`), `LiveFillScreen.tsx` (pass `kind`), `en.json`
- Test: `LiveFillScreen.test.tsx` (Word form describe)

- [ ] **Step 1: Failing tests:** `I answer a declaration with Yes`: in the card of the first declaration, `getByRole("radio", { name: "Yes" })` click → PATCH value `"yes"`, the zone shows "Yes"; `Clear` → PATCH `null`. `a stored "Yes" shows as selected` (Review Focus 4): answer value `"Yes"` → radio Yes checked.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** a radio group (two buttons with `role="radio"`/`aria-checked`, or shadcn ToggleGroup if added via `pnpm dlx shadcn@latest add toggle-group`), labelled by the field label; saves at once; keyboard Enter on the card focuses the selected (or first) option.
- [ ] **Step 4: Run** front checks → PASS.
- [ ] **Step 5: Commit** `feat(review-queue): Yes/No declarations answered with buttons`.

### Task 5: Front — Auto-fill disabled for Word forms

**Files:**
- Modify: `frontend/src/features/tender/FormList.tsx`, `en.json`
- Test: `frontend/src/screens/tender/TenderScreen.test.tsx`, `frontend/src/shared/test/fixtures/tender.ts` (Annex 4 summary with counts)

- [ ] **Step 1: Failing test:** `a Word form shows what was detected but cannot be auto-filled yet`: Annex 4 card text "49 fields detected · 17 Yes/No declarations · 1 signature"; `Auto-fill` button disabled with tooltip/title "Auto-fill for Word forms is coming soon"; a started Word form still shows `Continue review`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (`// Temporary (step 6c): Word forms are not auto-filled yet.`). **Step 4: Run** front checks → PASS.
- [ ] **Step 5: Commit** `feat(tender): Word forms listed with their fields, auto-fill coming soon`.

### Task 6: e2e and docs

**Files:**
- Modify: `frontend/e2e/main-scenario.spec.ts`, `docs/PLAN.md` (6b section), `docs/ARCHITECTURE.md` (Word preview line), `CLAUDE.md` only with the user's validation.

- [ ] **Step 1: Extend the scenario** (before the discard at the end): Annex 4 card shows "49 fields detected" and a disabled `Auto-fill`; `page.goto(/forms/{annex4Id}/fill)` (id from the card's form list API response or `page.request.get`); the Word preview shows "Exact company name"; type "Alpenlogic AG" in "Exact company name" → visible in the preview; answer the first declaration Yes; Export DOCX → download named `Annex_4_Conditions of Participation and Company Self-Declaration.docx`, starts with `PK`.
- [ ] **Step 2: Run** `pnpm e2e` → PASS.
- [ ] **Step 3: Docs**: PLAN.md 6b entry (what was built, limits: `docx-preview` approximations, 2 rendered pages for 3 Word pages, Auto-fill disabled until 6c).
- [ ] **Step 4: Commit** `test(e2e): Annex 4 filled by hand and exported; docs for 6b`.
