"""Text extraction on the real company documents, plus unreadable files."""

import io

import docx
import pymupdf
import pytest

from app.modules.knowledge.extraction import UnreadableDocumentError, extract_docx, extract_pdf
from tests.modules.helpers import demo_document


def _read(file_name: str) -> bytes:
    return (demo_document(file_name)).read_bytes()


def test_a_pdf_gives_its_pages_and_each_block_where_it_sits() -> None:
    extracted = extract_pdf(_read("01_commercial_register_extract.pdf"))

    assert extracted.pages == 2
    [uid] = [block for block in extracted.blocks if "CHE-123.456.789" in block.text]
    assert uid.text == "UID\nCHE-123.456.789"
    assert uid.page == 0
    assert uid.box is not None
    assert 0 < uid.box.x0 < uid.box.x1 < 595
    assert 0 < uid.box.y0 < uid.box.y1 < 842
    assert {block.page for block in extracted.blocks} == {0, 1}


def test_pdf_blocks_come_in_reading_order() -> None:
    blocks = extract_pdf(_read("01_commercial_register_extract.pdf")).blocks
    texts = [block.text for block in blocks]

    assert texts.index("Company name\nAlpenlogic AG") < texts.index("UID\nCHE-123.456.789")
    # Top to bottom by the line each block ends on (PyMuPDF's sort).
    first_page = [block.box for block in blocks if block.page == 0 and block.box]
    assert [box.y1 for box in first_page] == sorted(box.y1 for box in first_page)


def test_a_word_document_gives_paragraphs_headings_and_table_rows() -> None:
    extracted = extract_docx(_read("10_hr_compliance_policy.docx"))

    assert extracted.pages is None
    headings = [block.text for block in extracted.blocks if block.heading]
    assert "3. Occupational health and safety" in headings
    assert any("SVA Zurich, Röntgenstrasse 17" in block.text for block in extracted.blocks)
    # Table rows: one block per row, cells joined.
    assert any(" | " in block.text for block in extracted.blocks)
    assert all(block.page is None and block.box is None for block in extracted.blocks)


def test_word_table_cells_merged_across_columns_appear_once() -> None:
    document = docx.Document()
    table = document.add_table(rows=1, cols=3)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Share capital"
    table.cell(0, 2).text = "CHF 500,000"
    buffer = io.BytesIO()
    document.save(buffer)

    [row] = extract_docx(buffer.getvalue()).blocks

    assert row.text == "Share capital | CHF 500,000"


@pytest.mark.parametrize("extract", [extract_pdf, extract_docx])
def test_a_file_that_is_not_a_document_is_unreadable(extract) -> None:
    with pytest.raises(UnreadableDocumentError):
        extract(b"definitely not a document")


def test_a_pdf_without_text_is_unreadable() -> None:
    document = pymupdf.open()
    document.new_page()

    with pytest.raises(UnreadableDocumentError, match="scan"):
        extract_pdf(document.tobytes())
