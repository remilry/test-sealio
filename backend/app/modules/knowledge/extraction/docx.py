"""Word → text blocks in document order: paragraphs (headings marked) and table rows."""

import io
import zipfile

import docx
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.modules.knowledge.extraction.blocks import (
    ExtractedDocument,
    TextBlock,
    UnreadableDocumentError,
)


def extract_docx(content: bytes) -> ExtractedDocument:
    try:
        document = docx.Document(io.BytesIO(content))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as error:
        raise UnreadableDocumentError("This file is not a readable Word document.") from error
    blocks: list[TextBlock] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            if text := item.text.strip():
                blocks.append(TextBlock(text=text, heading=_is_heading(item)))
        elif isinstance(item, Table):
            blocks.extend(TextBlock(text=row) for row in _table_rows(item))
    if not blocks:
        raise UnreadableDocumentError("No text found in this Word document.")
    return ExtractedDocument(pages=None, blocks=blocks)


def _is_heading(paragraph: Paragraph) -> bool:
    style = (paragraph.style.name if paragraph.style is not None else None) or ""
    return style.startswith("Heading") or style == "Title"


def _table_rows(table: Table) -> list[str]:
    """One line per row, cells separated by " | " (merged cells repeated by Word appear once)."""
    rows = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            text = " ".join(cell.text.split())
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))
    return rows
