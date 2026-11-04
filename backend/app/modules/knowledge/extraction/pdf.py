"""PDF → text blocks with their page and rectangle (PyMuPDF): a citation can be shown in place."""

import pymupdf

from app.modules.knowledge.extraction.blocks import (
    Box,
    ExtractedDocument,
    TextBlock,
    UnreadableDocumentError,
)

# PyMuPDF block type of text blocks (1 is an image).
_TEXT_BLOCK = 0


def extract_pdf(content: bytes) -> ExtractedDocument:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        raise UnreadableDocumentError("This file is not a readable PDF.") from error
    with document:
        blocks = [
            TextBlock(
                text=text,
                page=page.number,
                box=Box(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1)),
            )
            for page in document
            # sort=True: top to bottom, then left to right (reading order of these layouts).
            for x0, y0, x1, y1, raw, _no, kind in page.get_text("blocks", sort=True)
            if kind == _TEXT_BLOCK and (text := str(raw).strip())
        ]
        if not blocks:
            raise UnreadableDocumentError("No text found in this PDF (is it a scan?).")
        return ExtractedDocument(pages=document.page_count, blocks=blocks)
