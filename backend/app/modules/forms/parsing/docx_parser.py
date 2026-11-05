"""Word form (DOCX, no content controls) → FormSchema. Pure: bytes in, data out.

Generic rules on the document's structure, with no knowledge of any specific form
(docs/superpowers/specs/2026-11-05-6a-docx-parse-export-design.md §3):

- a table row "label | empty cell": the answer goes into the empty cell;
- in a cell, each short paragraph is a label: the answer goes into the empty paragraph below it,
  or after the label when it ends with ":", or else into a new paragraph below it;
- a table whose header row mentions "Yes/No": each question with an empty answer cell is a Yes/No;
- dot leaders in a paragraph: the answer replaces them;
- outside tables, a label ending with ":" followed by tabs, and a signature/stamp label;
- not fields: long text, a heading row (one cell, one label without ":"), a label that heads
  several labels on its right, the header row of a Yes/No table.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass

from docx import Document
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from app.modules.forms.parsing.labels import SIGNATURE_LABEL, clean_label, leader_runs, unique_key
from app.modules.forms.parsing.schema import (
    DocxLocator,
    DocxWriteMode,
    FieldKind,
    FormSchema,
    ParsedField,
)

# A label is a short paragraph: longer text is an explanation, never a field.
MAX_LABEL_CHARS = 120
YES_NO_HEADER = re.compile(r"\byes\s*/\s*no\b", re.IGNORECASE)
BODY_SECTION = "Text"


@dataclass
class _Blank:
    label: str
    section: str
    kind: FieldKind
    locator: DocxLocator


def parse_docx(data: bytes) -> FormSchema:
    document = Document(io.BytesIO(data))
    blanks: list[_Blank] = []
    body_paragraph, table_index = 0, 0
    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            paragraph = Paragraph(element, document)
            blanks.extend(_body_blanks(paragraph, body_paragraph))
            body_paragraph += 1
        elif element.tag.endswith("}tbl"):
            blanks.extend(_table_blanks(Table(element, document), table_index))
            table_index += 1
    seen: set[str] = set()
    return FormSchema(
        pages=[],
        fields=[
            ParsedField(
                key=unique_key(blank.label, seen),
                section=blank.section,
                label=blank.label,
                kind=blank.kind,
                locator=blank.locator,
            )
            for blank in blanks
        ],
    )


# --- Paragraph helpers ----------------------------------------------------------------------


def _text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _blank(paragraph: Paragraph) -> bool:
    return not _text(paragraph).strip()


def _kind(label: str) -> FieldKind:
    return FieldKind.SIGNATURE if SIGNATURE_LABEL.search(label) else FieldKind.TEXT


def _last_text_run(paragraph: Paragraph) -> int:
    """Index of the last run holding visible text (the label's end)."""
    runs = paragraph.runs
    return max(index for index, run in enumerate(runs) if run.text.strip())


def _run_at(paragraph: Paragraph, char_index: int) -> int:
    """Index of the run holding the paragraph's character at char_index."""
    position = 0
    for index, run in enumerate(paragraph.runs):
        position += len(run.text)
        if char_index < position:
            return index
    return len(paragraph.runs) - 1


def _leader_blank(paragraph: Paragraph) -> tuple[str, int] | None:
    """(label, run holding the dots) for a paragraph with a dot leader."""
    text = _text(paragraph)
    runs = leader_runs(text)
    if not runs:
        return None
    label = text
    for start, end in reversed(runs):
        label = label[:start] + "…" + label[end:]
    return clean_label(label), _run_at(paragraph, runs[0][0])


def _segments(paragraph: Paragraph) -> list[tuple[str, int, bool]]:
    """The paragraph's text split at its tabs: (text, run of its last character, tab after it)."""
    segments: list[tuple[str, int, bool]] = []
    current, last_run = "", 0
    for index, run in enumerate(paragraph.runs):
        for char in run.text:
            if char == "\t":
                if current.strip():
                    segments.append((current, last_run, True))
                current = ""
                continue
            current += char
            if not char.isspace():
                last_run = index
    if current.strip():
        segments.append((current, last_run, False))
    return segments


# --- Body paragraphs ------------------------------------------------------------------------


def _body_blanks(paragraph: Paragraph, index: int) -> list[_Blank]:
    leader = _leader_blank(paragraph)
    if leader is not None:
        label, run = leader
        return [_body_blank(label, index, DocxWriteMode.REPLACE_LEADER, run)]
    blanks: list[_Blank] = []
    for text, run, tab_after in _segments(paragraph):
        stripped = text.strip()
        if len(stripped) > MAX_LABEL_CHARS:
            continue
        label = clean_label(stripped)
        is_signature = bool(SIGNATURE_LABEL.search(label))
        if label and (is_signature or (stripped.endswith(":") and tab_after)):
            blanks.append(_body_blank(label, index, DocxWriteMode.IN_PARAGRAPH, run))
    return blanks


def _body_blank(label: str, index: int, mode: DocxWriteMode, run: int | None) -> _Blank:
    return _Blank(
        label=label,
        section=BODY_SECTION,
        kind=_kind(label),
        locator=DocxLocator(paragraph=index, mode=mode, after_run=run),
    )


# --- Tables ---------------------------------------------------------------------------------


def _distinct_cells(row_cells: list[_Cell]) -> list[_Cell]:
    """The row's cells, a merged cell once, without the continuations of vertical merges."""
    cells: list[_Cell] = []
    for cell in row_cells:
        if cells and cell._tc is cells[-1]._tc:  # pyright: ignore[reportPrivateUsage]
            continue
        cells.append(cell)
    return [cell for cell in cells if cell._tc.vMerge != "continue"]  # pyright: ignore[reportPrivateUsage]


def _cell_blank(cell: _Cell) -> bool:
    return all(_blank(paragraph) for paragraph in cell.paragraphs)


def _labels(cell: _Cell) -> list[str]:
    return [_text(p).strip() for p in cell.paragraphs if not _blank(p)]


def _table_blanks(table: Table, table_index: int) -> list[_Blank]:
    section = f"Table {table_index + 1}"
    rows = [_distinct_cells(list(row.cells)) for row in table.rows]
    yes_no = bool(rows) and any(
        YES_NO_HEADER.search(_text(p)) for c in rows[0] for p in c.paragraphs
    )
    blanks: list[_Blank] = []
    for row_index, cells in enumerate(rows):
        if yes_no and row_index == 0:
            continue
        locate = _Row(table_index, row_index).locator
        if yes_no and len(cells) >= 2 and _cell_blank(cells[-1]) and not _cell_blank(cells[0]):
            label = clean_label(" ".join(_labels(cells[0])))
            locator = locate(len(cells) - 1, 0, DocxWriteMode.IN_PARAGRAPH)
            blanks.append(_Blank(label, section, FieldKind.YES_NO, locator))
            continue
        heading_row = len(cells) == 1 and _is_heading(cells[0])
        if heading_row:
            continue
        for cell_index, cell in enumerate(cells):
            if _cell_blank(cell):
                continue
            following = cells[cell_index + 1] if cell_index + 1 < len(cells) else None
            if following is not None and _cell_blank(following):
                labels = _labels(cell)
                if len(labels) == 1 and len(labels[0]) <= MAX_LABEL_CHARS:
                    label = clean_label(labels[0])
                    locator = locate(cell_index + 1, 0, DocxWriteMode.IN_PARAGRAPH)
                    blanks.append(_Blank(label, section, _kind(label), locator))
                continue
            if following is not None and len(_labels(following)) > 1:
                continue  # heads the labels on its right
            blanks.extend(_in_cell_blanks(cell, cell_index, section, locate))
    return blanks


@dataclass(frozen=True)
class _Row:
    table: int
    row: int

    def locator(
        self, cell: int, paragraph: int, mode: DocxWriteMode, run: int | None = None
    ) -> DocxLocator:
        return DocxLocator(
            table=self.table,
            row=self.row,
            cell=cell,
            paragraph=paragraph,
            mode=mode,
            after_run=run,
        )


def _is_heading(cell: _Cell) -> bool:
    """A lone label without ":" and no room below it: the title of the rows that follow."""
    labels = _labels(cell)
    paragraphs = cell.paragraphs
    return (
        len(labels) == 1
        and not labels[0].rstrip().endswith(":")
        and not _blank(paragraphs[0])
        and (len(paragraphs) == 1 or not _blank(paragraphs[1]))
    )


def _in_cell_blanks(
    cell: _Cell, cell_index: int, section: str, locate: Callable[..., DocxLocator]
) -> list[_Blank]:
    paragraphs = cell.paragraphs
    leaders = [(index, _leader_blank(p)) for index, p in enumerate(paragraphs)]
    if any(leader for _, leader in leaders):
        # A cell that marks its blanks with dot leaders: only those are fields.
        return [
            _Blank(
                leader[0],
                section,
                _kind(leader[0]),
                locate(cell_index, index, DocxWriteMode.REPLACE_LEADER, leader[1]),
            )
            for index, leader in leaders
            if leader is not None
        ]
    blanks: list[_Blank] = []
    for index, paragraph in enumerate(paragraphs):
        text = _text(paragraph).strip()
        if not text or len(text) > MAX_LABEL_CHARS:
            continue
        label = clean_label(text)
        below = paragraphs[index + 1] if index + 1 < len(paragraphs) else None
        if below is not None and _blank(below):
            locator = locate(cell_index, index + 1, DocxWriteMode.IN_PARAGRAPH)
        elif text.endswith(":"):
            locator = locate(
                cell_index, index, DocxWriteMode.IN_PARAGRAPH, _last_text_run(paragraph)
            )
        else:
            locator = locate(cell_index, index, DocxWriteMode.NEW_PARAGRAPH)
        blanks.append(_Blank(label, section, _kind(label), locator))
    return blanks
