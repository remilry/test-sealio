"""How a DocxLocator addresses a Word document, shared by the parser and the exporter (pure)."""

from docx.document import Document
from docx.table import _Cell, _Row  # pyright: ignore[reportPrivateUsage]
from docx.text.paragraph import Paragraph

from app.modules.forms.parsing.schema import DocxLocator


def distinct_cells(row: _Row) -> list[_Cell]:
    """The row's own cells: a merged cell once, without the continuations of a vertical merge
    (python-docx's `row.cells` repeats the cell above for those)."""
    return [
        _Cell(tc, row.table)
        for tc in row._tr.tc_lst  # pyright: ignore[reportPrivateUsage]
        if tc.vMerge != "continue"
    ]


def paragraph_at(document: Document, locator: DocxLocator) -> Paragraph:
    """The paragraph the locator points at (for a new paragraph: the label's, it goes after)."""
    if locator.table is None:
        return document.paragraphs[locator.paragraph]
    assert locator.row is not None
    assert locator.cell is not None
    row = document.tables[locator.table].rows[locator.row]
    return distinct_cells(row)[locator.cell].paragraphs[locator.paragraph]
