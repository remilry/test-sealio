"""Common representation of a buyer form, whatever its file format (pure data, no I/O)."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class FieldKind(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    YES_NO = "yes_no"
    # Signature or stamp: shown, never filled (docs/USER_FLOW.md §4).
    SIGNATURE = "signature"


class Box(BaseModel):
    """A rectangle in PDF points, origin at the top-left corner of the page (PyMuPDF convention)."""

    x0: float
    y0: float
    x1: float
    y1: float


class PdfLocator(BaseModel):
    """Where a field's answer goes in a flat PDF."""

    format: Literal["pdf"] = "pdf"
    page: int  # 0-based
    # Area the answer is written into (also the zone highlighted in the preview).
    box: Box
    # Baseline and font size of the surrounding text, so the answer sits on the line.
    baseline: float
    font_size: float
    # Placeholder marks (dot leaders) removed when the field gets a value.
    erase: list[Box] = []


class DocxWriteMode(StrEnum):
    # After run `after_run` of the paragraph, or at its end (also an empty paragraph or cell).
    IN_PARAGRAPH = "in_paragraph"
    # In a new paragraph inserted right after `paragraph` (a label alone in its cell).
    NEW_PARAGRAPH = "new_paragraph"
    # In place of the dot leader held by run `after_run`.
    REPLACE_LEADER = "replace_leader"


class DocxLocator(BaseModel):
    """Where a field's answer goes in a Word document (python-docx indexes)."""

    format: Literal["docx"] = "docx"
    # Index among the body's tables; None for a paragraph of the body itself.
    table: int | None = None
    row: int | None = None
    # Index among the distinct cells of the row (a merged cell counts once).
    cell: int | None = None
    # Index of the paragraph in the cell, or among the body's paragraphs outside tables.
    paragraph: int
    mode: DocxWriteMode
    after_run: int | None = None


Locator = Annotated[PdfLocator | DocxLocator, Field(discriminator="format")]


class ParsedField(BaseModel):
    key: str
    section: str
    label: str
    kind: FieldKind
    locator: Locator


class PageSize(BaseModel):
    width: float
    height: float


class FormSchema(BaseModel):
    pages: list[PageSize]
    fields: list[ParsedField]
