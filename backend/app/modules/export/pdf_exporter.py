"""Write answers into the original flat PDF. Pure: bytes in, bytes out.

For each answered field: the placeholder marks (dot leaders) are removed, then the value is
written on the field's baseline, inside its box, shrinking the font if it would overflow.
Everything else (text, images, rules) is left as it was.
"""

import pymupdf

from app.modules.forms.parsing.schema import PdfLocator

FONT = pymupdf.Font("helv")
MIN_FONT_SIZE = 5.0
TEXT_COLOR = (0.0, 0.0, 0.0)


def export_pdf(original: bytes, answers: list[tuple[PdfLocator, str]]) -> bytes:
    with pymupdf.open(stream=original, filetype="pdf") as doc:
        by_page: dict[int, list[tuple[PdfLocator, str]]] = {}
        for locator, value in answers:
            if value.strip():
                by_page.setdefault(locator.page, []).append((locator, " ".join(value.split())))
        for page_index, page_answers in by_page.items():
            page = doc[page_index]
            _erase_placeholders(page, [locator for locator, _ in page_answers])
            writer = pymupdf.TextWriter(page.rect)
            for locator, value in page_answers:
                _write(writer, locator, value)
            writer.write_text(page, color=TEXT_COLOR)
        return doc.tobytes(garbage=3, deflate=True)


def _erase_placeholders(page: pymupdf.Page, locators: list[PdfLocator]) -> None:
    boxes = [box for locator in locators for box in locator.erase]
    if not boxes:
        return
    for box in boxes:
        # Slightly inset so the neighbouring characters (the label) are never touched.
        rect = pymupdf.Rect(box.x0 + 0.3, box.y0 + 0.5, box.x1 - 0.3, box.y1 - 0.5)
        page.add_redact_annot(rect, fill=None)  # no fill: only the marks go
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )


def fitting_font_size(value: str, width: float, preferred: float) -> float:
    """The preferred size, or the largest smaller one that fits the width (floor MIN_FONT_SIZE)."""
    length = FONT.text_length(value, fontsize=preferred)  # pyright: ignore[reportArgumentType]
    if length <= width:
        return preferred
    return max(MIN_FONT_SIZE, preferred * width / length)


def _write(writer: pymupdf.TextWriter, locator: PdfLocator, value: str) -> None:
    box = locator.box
    size = fitting_font_size(value, box.x1 - box.x0, locator.font_size)
    writer.append((box.x0, locator.baseline), value, font=FONT, fontsize=size)  # pyright: ignore[reportArgumentType]
