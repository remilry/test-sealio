"""Common representation of a buyer form, whatever its file format (pure data, no I/O)."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


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


class ParsedField(BaseModel):
    key: str
    section: str
    label: str
    kind: FieldKind
    locator: PdfLocator


class PageSize(BaseModel):
    width: float
    height: float


class FormSchema(BaseModel):
    pages: list[PageSize]
    fields: list[ParsedField]
