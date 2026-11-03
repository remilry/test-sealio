"""Flat PDF (no AcroForm fields) → FormSchema. Pure: bytes in, data out.

Two generic kinds of blanks are detected, with no knowledge of any specific form:

- **Dot leaders**: a run of `…` / `.` characters, labelled by the text before it on the same line,
  or by the nearest text on the same baseline to its left, or by the line just above.
- **Empty table cells**: a cell drawn with rules that holds a single short label and free space
  on its right; the answer goes on the label's line, to its right.
"""

import re
from dataclasses import dataclass, field
from typing import Any, cast

import pymupdf

from app.modules.forms.parsing.schema import (
    Box,
    FieldKind,
    FormSchema,
    PageSize,
    ParsedField,
    PdfLocator,
)

# Weight of each placeholder character: a run must weigh at least MIN_LEADER_WEIGHT
# (two ellipses, or six periods) so that "..." ending a sentence is not a field.
LEADER_WEIGHTS = {"…": 3, ".": 1}
MIN_LEADER_WEIGHT = 6
# A rule is a filled rectangle (or a line) thinner than this, in points.
RULE_THICKNESS = 2.0
# Tolerance when comparing coordinates, in points.
TOLERANCE = 1.5
# A table cell must leave at least this much free width to the right of its label.
MIN_CELL_FREE_WIDTH = 40.0
SIGNATURE_LABEL = re.compile(r"\b(signature|stamp)", re.IGNORECASE)


@dataclass
class _Char:
    c: str
    x0: float
    y0: float
    x1: float
    y1: float
    baseline: float
    size: float


@dataclass
class _Line:
    chars: list[_Char]
    used: bool = field(default=False)

    @property
    def text(self) -> str:
        return "".join(ch.c for ch in self.chars).strip()

    @property
    def x0(self) -> float:
        return self.chars[0].x0

    @property
    def x1(self) -> float:
        return self.chars[-1].x1

    @property
    def y0(self) -> float:
        return min(ch.y0 for ch in self.chars)

    @property
    def y1(self) -> float:
        return max(ch.y1 for ch in self.chars)

    @property
    def baseline(self) -> float:
        return self.chars[0].baseline

    @property
    def size(self) -> float:
        return max(ch.size for ch in self.chars)


@dataclass(frozen=True)
class _Rule:
    """A horizontal (`at` = y, from `start` to `end` in x) or vertical (`at` = x, y range) rule."""

    at: float
    start: float
    end: float

    def covers(self, value: float) -> bool:
        return self.start - TOLERANCE <= value <= self.end + TOLERANCE


@dataclass
class _Blank:
    label: str
    locator: PdfLocator


def parse_pdf(data: bytes) -> FormSchema:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages: list[PageSize] = []
        blanks: list[_Blank] = []
        for page_index in range(doc.page_count):
            page = doc[page_index]
            pages.append(PageSize(width=page.rect.width, height=page.rect.height))
            lines = _text_lines(page)
            if not lines:
                continue
            page_blanks = _dot_leaders(page_index, lines) + _table_cells(
                page_index, lines, _rules(page)
            )
            page_blanks.sort(key=lambda b: (round(b.locator.baseline), b.locator.box.x0))
            blanks.extend(page_blanks)
    return FormSchema(pages=pages, fields=_to_fields(blanks))


def _text_lines(page: pymupdf.Page) -> list[_Line]:
    lines: list[_Line] = []
    raw = cast(dict[str, Any], page.get_text("rawdict"))
    for block in raw["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            chars = [
                _Char(
                    c=ch["c"],
                    x0=ch["bbox"][0],
                    y0=ch["bbox"][1],
                    x1=ch["bbox"][2],
                    y1=ch["bbox"][3],
                    baseline=ch["origin"][1],
                    size=span["size"],
                )
                for span in line["spans"]
                for ch in span["chars"]
            ]
            if "".join(ch.c for ch in chars).strip():
                lines.append(_Line(chars))
    return lines


# --- Dot leaders -----------------------------------------------------------------------------


def _leader_runs(line: _Line) -> list[tuple[int, int]]:
    """[start, end) indexes of the placeholder runs of a line."""
    runs: list[tuple[int, int]] = []
    start = None
    for index, ch in enumerate([*line.chars, None]):
        if ch is not None and ch.c in LEADER_WEIGHTS:
            if start is None:
                start = index
            continue
        if start is not None:
            weight = sum(LEADER_WEIGHTS[c.c] for c in line.chars[start:index])
            if weight >= MIN_LEADER_WEIGHT:
                runs.append((start, index))
            start = None
    return runs


def _dot_leaders(page_index: int, lines: list[_Line]) -> list[_Blank]:
    right_margin = max(line.x1 for line in lines)
    blanks: list[_Blank] = []
    for line in lines:
        runs = _leader_runs(line)
        if runs:
            line.used = True
        previous_end = 0
        for start, end in runs:
            run = line.chars[start:end]
            label = _clean_label("".join(ch.c for ch in line.chars[previous_end:start]))
            label = label or _label_on_the_left(line, run[0].x0, lines)
            label = label or _label_above(line, lines)
            previous_end = end
            if not label:
                continue
            # Write up to the next text on the line, or to the page's text margin.
            obstacles = [ch.x0 for ch in line.chars[end:] if not ch.c.isspace()]
            obstacles += [
                other.x0
                for other in lines
                if other is not line
                and abs(other.baseline - line.baseline) < TOLERANCE
                and other.x0 >= run[-1].x1
            ]
            right = min(obstacles) - 2 if obstacles else max(run[-1].x1, right_margin)
            blanks.append(
                _Blank(
                    label=label,
                    locator=PdfLocator(
                        page=page_index,
                        box=Box(
                            x0=run[0].x0,
                            y0=min(ch.y0 for ch in run),
                            x1=right,
                            y1=max(ch.y1 for ch in run),
                        ),
                        baseline=run[0].baseline,
                        font_size=run[0].size,
                        erase=[
                            Box(
                                x0=run[0].x0,
                                y0=min(ch.y0 for ch in run),
                                x1=run[-1].x1,
                                y1=max(ch.y1 for ch in run),
                            )
                        ],
                    ),
                )
            )
    return blanks


def _label_on_the_left(line: _Line, x: float, lines: list[_Line]) -> str:
    candidates = [
        other
        for other in lines
        if other is not line
        and abs(other.baseline - line.baseline) < TOLERANCE
        and other.x1 <= x + TOLERANCE
        and not _leader_runs(other)
    ]
    if not candidates:
        return ""
    nearest = max(candidates, key=lambda other: other.x1)
    nearest.used = True
    return _clean_label(nearest.text)


def _label_above(line: _Line, lines: list[_Line]) -> str:
    candidates = [
        other
        for other in lines
        if other is not line
        and other.y1 <= line.y0 + TOLERANCE
        and other.y1 >= line.y0 - 2 * line.size
        and other.x0 < line.x1
        and other.x1 > line.x0
        and not _leader_runs(other)
    ]
    if not candidates:
        return ""
    nearest = max(candidates, key=lambda other: other.y1)
    nearest.used = True
    return _clean_label(nearest.text)


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip()


# --- Table cells -----------------------------------------------------------------------------


def _rules(page: pymupdf.Page) -> tuple[list[_Rule], list[_Rule]]:
    """Horizontal and vertical rules drawn on the page (thin rectangles, lines, cell borders)."""
    horizontal: list[_Rule] = []
    vertical: list[_Rule] = []

    def add_rect(rect: pymupdf.Rect, stroked: bool) -> None:
        if rect.height <= RULE_THICKNESS and rect.width > RULE_THICKNESS:
            horizontal.append(_Rule((rect.y0 + rect.y1) / 2, rect.x0, rect.x1))
        elif rect.width <= RULE_THICKNESS and rect.height > RULE_THICKNESS:
            vertical.append(_Rule((rect.x0 + rect.x1) / 2, rect.y0, rect.y1))
        elif stroked:
            horizontal.extend([_Rule(rect.y0, rect.x0, rect.x1), _Rule(rect.y1, rect.x0, rect.x1)])
            vertical.extend([_Rule(rect.x0, rect.y0, rect.y1), _Rule(rect.x1, rect.y0, rect.y1)])

    for path in page.get_drawings():
        stroked = "s" in (path.get("type") or "")
        for item in path["items"]:
            if item[0] == "re":
                add_rect(pymupdf.Rect(item[1]), stroked)
            elif item[0] == "l":
                p1, p2 = item[1], item[2]
                add_rect(pymupdf.Rect(p1, p2).normalize(), stroked=False)
    return horizontal, vertical


def _table_cells(
    page_index: int, lines: list[_Line], rules: tuple[list[_Rule], list[_Rule]]
) -> list[_Blank]:
    horizontal, vertical = rules
    blanks: list[_Blank] = []
    for line in lines:
        if line.used:
            continue
        cx, cy = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
        tops = [r.at for r in horizontal if r.at <= line.y0 + TOLERANCE and r.covers(cx)]
        bottoms = [r.at for r in horizontal if r.at >= line.y1 - TOLERANCE and r.covers(cx)]
        lefts = [r.at for r in vertical if r.at <= line.x0 + TOLERANCE and r.covers(cy)]
        rights = [r.at for r in vertical if r.at >= line.x1 - TOLERANCE and r.covers(cy)]
        if not (tops and bottoms and lefts and rights):
            continue
        top, bottom, left, right = max(tops), min(bottoms), max(lefts), min(rights)
        if bottom - top > 4 * (line.y1 - line.y0) or right - line.x1 < MIN_CELL_FREE_WIDTH:
            continue
        alone = not any(
            other is not line
            and left < (other.x0 + other.x1) / 2 < right
            and top < (other.y0 + other.y1) / 2 < bottom
            for other in lines
        )
        if not alone:
            continue
        gap = line.size * 0.6
        blanks.append(
            _Blank(
                label=_clean_label(line.text),
                locator=PdfLocator(
                    page=page_index,
                    box=Box(x0=line.x1 + gap, y0=line.y0, x1=right - gap / 2, y1=line.y1),
                    baseline=line.baseline,
                    font_size=line.size,
                ),
            )
        )
    return blanks


# --- Fields ----------------------------------------------------------------------------------


def _to_fields(blanks: list[_Blank]) -> list[ParsedField]:
    fields: list[ParsedField] = []
    seen: set[str] = set()
    for blank in blanks:
        key = _unique_key(blank.label, seen)
        fields.append(
            ParsedField(
                key=key,
                section=f"Page {blank.locator.page + 1}",
                label=blank.label,
                kind=FieldKind.SIGNATURE if SIGNATURE_LABEL.search(blank.label) else FieldKind.TEXT,
                locator=blank.locator,
            )
        )
    return fields


def _unique_key(label: str, seen: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:60] or "field"
    key, suffix = base, 2
    while key in seen:
        key, suffix = f"{base}_{suffix}", suffix + 1
    seen.add(key)
    return key
