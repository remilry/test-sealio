# 6a — DOCX parser and exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the Annex 4 Word form into the common `FormSchema` and write answers back into the original DOCX, layout untouched — back end only, pure and tested.

**Architecture:** A pure `parse_docx(bytes) -> FormSchema` next to `parse_pdf`, sharing label/key/leader helpers; a `DocxLocator` (table/row/cell/paragraph + write mode) joins `PdfLocator` in a discriminated union; a pure `export_docx(bytes, answers) -> bytes` next to `export_pdf`, picked by `export/service.py` from the form's format. The parser is **not** registered in `forms_service.PARSERS` yet (6b).

**Tech Stack:** Python 3.14, python-docx (already a dependency), Pydantic, pytest; front: `make gen-api` + a type narrowing only.

**Spec:** `docs/superpowers/specs/2026-11-05-6a-docx-parse-export-design.md`

## Global Constraints

- No rule specific to Annex 4: no hard-coded label, table index or key in `app/` (only in tests).
- Parser and exporter are pure (bytes in, data/bytes out, no I/O, no DB).
- Signature fields are never written. Yes/No written as `Yes` / `No`.
- Nothing outside the paragraphs of filled fields changes in the exported DOCX.
- Sections: `Table {n}` (1-based, in body order) and `Text` for fields outside tables. Keys: same normalisation as PDF, `_2`, `_3`… on duplicates.
- Backend checks: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run pyright`. Front: `pnpm typecheck` / `pnpm lint` / `pnpm test` (see `frontend/CLAUDE.md`).
- `forms_service.PARSERS` stays PDF-only; `tests/modules/forms/test_api.py::test_a_word_form_has_no_fields_yet` must still pass.

## Review Focus

1. A label run followed by tabs then more text on the same line ("Place and date: ⇥⇥⇥⇥⇥ Company stamp…"): the value must not push the trailing text onto a new line → tab-absorption test in Task 4.
2. Merged cells (gridSpan / python-docx repeating the same `_tc`): a merged cell must yield one field, not one per grid column → "Remarks" row test in Task 2 and unique-locator assertion in Task 3.
3. Values with line breaks or surrounding spaces: written on one line, spaces normalised → exporter test in Task 4.
4. An empty or whitespace value, and a signature field in the answers list: document unchanged → exporter test in Task 4.
5. A cell that is long explanatory text with an empty paragraph after it (title table of Annex 4): not a field → synthetic test in Task 2 and expected schema in Task 3.

---

### Task 1: `DocxLocator`, locator union, shared label helpers

**Files:**
- Create: `backend/app/modules/forms/parsing/labels.py`
- Modify: `backend/app/modules/forms/parsing/schema.py`, `backend/app/modules/forms/parsing/pdf_parser.py`, `backend/app/modules/forms/schemas.py` (`FieldOut.locator`), `backend/app/modules/export/service.py` (narrow to PDF for now), `backend/app/modules/forms/models.py` (comment)
- Modify (front): `frontend/src/shared/api/schema.gen.ts` (via `make gen-api`), `frontend/src/screens/live-fill/LiveFillScreen.tsx` (narrow `field.locator.format === "pdf"`)
- Test: `backend/tests/modules/forms/test_schema.py`

**Interfaces:**
- Produces in `schema.py`:
  ```python
  class DocxWriteMode(StrEnum):
      IN_PARAGRAPH = "in_paragraph"      # after run `after_run`, or at the end / into an empty paragraph
      NEW_PARAGRAPH = "new_paragraph"    # a new paragraph inserted right after `paragraph`
      REPLACE_LEADER = "replace_leader"  # the dot leader in run `after_run` is replaced
  class DocxLocator(BaseModel):
      format: Literal["docx"] = "docx"
      table: int | None   # index among body tables; None = body paragraph
      row: int | None
      cell: int | None    # index among distinct cells of the row (merges counted once)
      paragraph: int      # index in the cell, or among body paragraphs when table is None
      mode: DocxWriteMode
      after_run: int | None = None
  Locator = Annotated[PdfLocator | DocxLocator, Field(discriminator="format")]
  ```
  `ParsedField.locator: Locator`; `FieldOut.locator: Locator`.
- Produces in `labels.py` (moved from `pdf_parser.py`, behaviour unchanged): `SIGNATURE_LABEL`, `LEADER_WEIGHTS`, `MIN_LEADER_WEIGHT`, `clean_label(text: str) -> str`, `unique_key(label: str, seen: set[str]) -> str`, `leader_runs(text: str) -> list[tuple[int, int]]` (string version: [start, end) of placeholder runs weighing ≥ `MIN_LEADER_WEIGHT`). `pdf_parser` uses them (its char-based `_leader_runs` may wrap the string version).

- [ ] **Step 1: Write the failing tests** in `test_schema.py`:
  - `test_a_field_locator_is_read_by_its_format`: `ParsedField.model_validate({... "locator": {"format": "docx", "table": 1, "row": 0, "cell": 1, "paragraph": 0, "mode": "in_paragraph"}})` → `isinstance(f.locator, DocxLocator)`; same with a PDF locator dict → `PdfLocator`.
  - `test_leader_runs_ignore_a_sentence_ending_ellipsis`: `leader_runs("Tender (No. ………., type of work)") == [(12, 17)]` (adjust indexes to the real string), `leader_runs("and so on...") == []`.
- [ ] **Step 2: Run** `uv run pytest tests/modules/forms/test_schema.py -v` → FAIL (import errors).
- [ ] **Step 3: Implement** the types and `labels.py`; switch `pdf_parser` to the helpers; in `export/service.py::export_file`, keep only `PdfLocator` answers (`isinstance`) — Task 5 adds DOCX.
- [ ] **Step 4: Run** `uv run pytest` (whole suite, PDF parser/exporter/API untouched) and `uv run pyright` → PASS.
- [ ] **Step 5: Front types:** `make gen-api` (repo root, API running or as documented), narrow in `LiveFillScreen.tsx` (skip non-PDF locators); `pnpm typecheck && pnpm lint && pnpm test` → PASS.
- [ ] **Step 6: Commit** `refactor(forms): locator union with DocxLocator, shared label helpers`.

### Task 2: `parse_docx` — the generic rules, on synthetic documents

**Files:**
- Create: `backend/app/modules/forms/parsing/docx_parser.py`
- Test: `backend/tests/modules/forms/test_docx_parser.py` (helper `_docx(build: Callable[[Document], None]) -> bytes` builds a document with python-docx in memory)

**Interfaces:**
- Consumes: Task 1 types and helpers.
- Produces: `parse_docx(data: bytes) -> FormSchema` (`pages=[]` — Word has no fixed pages; 6b may revisit). Body walked in order (`document.element.body` children: `w:p` and `w:tbl`); distinct cells = skip a cell whose `_tc` is the previous one's.

- [ ] **Step 1: Write the failing tests**, one per spec rule (§3), each asserting `[(f.label, f.kind, f.section, f.locator.mode, f.locator.table, f.locator.row, f.locator.cell, f.locator.paragraph, f.locator.after_run)]`:
  - `test_label_next_to_an_empty_cell` (rule 1): table row `"Exact company name" | ""` → `("Exact company name", text, "Table 1", in_paragraph, 0, 0, 1, 0, None)`.
  - `test_label_above_an_empty_paragraph` (rule 2): cell `["Insurance company:", ""]` → paragraph 1, `in_paragraph`, `after_run=None`.
  - `test_stacked_labels_with_colons` (rule 3): cell `["Business purpose:", "Main activity:", "Secondary activities:"]` → 3 fields, paragraphs 0/1/2, `in_paragraph`, `after_run` = index of the label's last run.
  - `test_label_ending_with_colon_and_tab` (rule 3): `"Legal form: \t"` → label `"Legal form"`, `in_paragraph` after its run.
  - `test_short_label_alone_in_its_cell` (rule 4): a row of 4 cells `"With professional training"`… → 4 fields, `new_paragraph`.
  - `test_yes_no_table` (rule 5): header row `["Self-declaration", "Answer: Yes/No"]`, two question rows with empty right cells, a merged `"Remarks:"` row with empty paragraphs → 2 `yes_no` fields (label = left cell text, answer in cell 1 paragraph 0) + 1 `text` "Remarks" (one field despite the merge).
  - `test_dot_leader_in_a_paragraph` (rule 6): `"Tender (No. ………., type of work)"` → label `"Tender (No. …, type of work)"`, `replace_leader`, `after_run` = run holding the dots.
  - `test_place_and_date_and_signature_outside_tables` (rule 7): body paragraph runs `["Place and date: ", "\t\t\t\t\t", "Company stamp and legally valid signature(s):"]` → `("Place and date", text, "Text", in_paragraph, None, None, None, <p index>, 0)` and `("Company stamp and legally valid signature(s)", signature, "Text", …)`.
  - `test_explanations_and_headings_are_not_fields` (rule 8, Review Focus 5): a cell with a 200-character sentence then `""`; a full-width heading row `"Number of employees in the area essential to performing the tendered contract"` above label rows; a long body paragraph ending with `:` → no field from them.
  - `test_duplicate_labels_get_unique_keys` (rule 10): two `"For foreign bidders, details of the pension scheme (exact address)"` → keys `…` and `…_2`.
- [ ] **Step 2: Run** `uv run pytest tests/modules/forms/test_docx_parser.py -v` → FAIL.
- [ ] **Step 3: Implement** `parse_docx`. Thresholds (max label length, "long text" detection) are the implementer's call; keep them as named module constants.
- [ ] **Step 4: Run** the file → PASS; `uv run pyright` → PASS.
- [ ] **Step 5: Commit** `feat(forms): generic Word form parser`.

### Task 3: Annex 4 expected schema

**Files:**
- Test: `backend/tests/modules/forms/test_docx_parser.py` (real-file tests, reading `get_settings().seed_forms_dir / "Annex_4_Conditions of Participation and Company Self-Declaration.docx"`)
- Modify: `docx_parser.py` only if a generic rule needs tuning (never an Annex-4-specific branch).

- [ ] **Step 1: Write the failing tests:**
  - `test_annex_4_fields`: the full expected list `[(key, label, kind, section)]` in reading order, ~49 fields as listed in the spec §3 (tender leader 1, identity 5, legal/company 9, employees 4, insurance 5, offices 5, 17 `yes_no`, Remarks, Place and date, 1 signature). Write it from the document's real labels (dump them once with the parser), checking each against the spec's list; sections `Table 1`…`Table 7` and `Text`.
  - `test_annex_4_locators_are_distinct`: no two fields share `(table, row, cell, paragraph, mode, after_run)`.
  - `test_annex_4_counts`: 17 `yes_no`, 1 `signature`.
- [ ] **Step 2: Run** → FAIL or PASS; tune generic rules until PASS, re-running Task 2's tests each time.
- [ ] **Step 3: Commit** `test(forms): Annex 4 expected schema`.

### Task 4: `export_docx`

**Files:**
- Create: `backend/app/modules/export/docx_exporter.py`
- Test: `backend/tests/modules/export/test_docx_exporter.py`

**Interfaces:**
- Consumes: `DocxLocator`, `parse_docx`.
- Produces: `export_docx(original: bytes, answers: list[tuple[DocxLocator, str]]) -> bytes`.

- [ ] **Step 1: Write the failing tests** (on the real Annex 4, values keyed by the Task 3 keys; reopen with python-docx; `_paragraph(doc, locator)` test helper resolves a locator):
  - `test_each_value_is_written_where_its_locator_points`: for each mode, the paragraph text contains the value right after the label (`in_paragraph`), equals it (empty paragraph / empty cell), is the paragraph right after the label (`new_paragraph`), or replaces the dots (`replace_leader`, no `…` left).
  - `test_a_written_value_uses_the_label_font`: the value's run has the label run's `rFonts` ascii font and `sz` (e.g. `HelveticaNeueLT Com 55 Roman`, size 20 half-points).
  - `test_yes_no_is_written_in_full`: answer `"yes"` / `"No"` → cell text `Yes` / `No`.
  - `test_tabs_absorb_the_place_and_date` (Review Focus 1): after writing `"Zurich, 05.11.2026"`, the paragraph has fewer tabs than before but ≥ 1, and still ends with `"Company stamp and legally valid signature(s):"`.
  - `test_values_are_written_on_one_line` (Review Focus 3): `"  Pfingstweidstrasse 31\n8005 Zurich "` → `"Pfingstweidstrasse 31 8005 Zurich"`.
  - `test_nothing_else_changes`: every package part except `word/document.xml` byte-identical; in `document.xml`, every body paragraph/cell not addressed by a filled locator has identical XML (`etree.tostring`).
  - `test_no_values_and_signatures_leave_the_document_unchanged` (Review Focus 4): answers `[(loc, "  ") …] + [(signature_loc, "Marc Keller")]` → `document.xml` identical to the original's.
- [ ] **Step 2: Run** `uv run pytest tests/modules/export/test_docx_exporter.py -v` → FAIL.
- [ ] **Step 3: Implement.** New run = deep copy of the label run's `w:rPr` (or of the paragraph mark's `w:pPr/w:rPr` for an empty paragraph); a leading space when the label does not end with a space or tab. Tab absorption: tabs directly following the label run, before other text, lose `ceil(value width / default tab stop)` tabs, keeping at least one; value width estimated as `len(value) × font size × 0.5` pt, default tab stop from `w:settings/w:defaultTabStop` (twips, 709 in Annex 4). Save with python-docx to bytes.
- [ ] **Step 4: Run** → PASS; `uv run pyright` → PASS.
- [ ] **Step 5: Commit** `feat(export): write answers into the original Word form`.

### Task 5: Export service by format, docs

**Files:**
- Modify: `backend/app/modules/export/service.py`
- Test: `backend/tests/modules/export/test_api.py`
- Modify: `docs/PLAN.md` (6a section under Étape 6, ✅ once validated), `docs/ARCHITECTURE.md` (parsing/export module lines: DOCX parser and exporter, `DocxLocator`)

**Interfaces:**
- Consumes: `export_docx`, `parse_docx`. The test gets a parsed Annex 4 with `monkeypatch.setitem(forms_service.PARSERS, FileFormat.DOCX, parse_docx)` **before** requesting the `client` fixture (each `TestClient(app)` seeds at startup on emptied tables), so the app's registry itself is unchanged.

- [ ] **Step 1: Write the failing test** `test_a_word_form_is_exported_as_word_under_its_original_name`: Annex 4 parsed (as above), `PATCH` one text field (`exact_company_name` → `"Alpenlogic AG"`), `GET /forms/{id}/export/file` → 200, `content-type` the DOCX media type, `content-disposition` file name = original, body reopened with python-docx contains `"Alpenlogic AG"` in table 1. Also `GET /forms/{id}/export` summary lists the Word form's empty fields and its signature.
- [ ] **Step 2: Run** → FAIL (`Export of Word forms is not available yet.`).
- [ ] **Step 3: Implement:** `export_file` dispatches on `form_file.file_format` → `export_pdf` with `PdfLocator` answers / `export_docx` with `DocxLocator` answers; the "not available" error goes.
- [ ] **Step 4: Run** `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run pyright` → PASS; front `pnpm typecheck && pnpm test` → PASS.
- [ ] **Step 5: Docs** — PLAN.md: 6a entry (parser rules in one paragraph, locator, exporter, tests, "parser registered in 6b"); ARCHITECTURE.md module lines.
- [ ] **Step 6: Commit** `feat(export): Word forms exported by the export API; docs for 6a`.
