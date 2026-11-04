"""Text of a company document, as extracted from its file (pure data, no I/O)."""

from pydantic import BaseModel


class Box(BaseModel):
    """A rectangle in PDF points, origin at the top-left corner of the page (PyMuPDF convention)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def union(self, other: Box) -> Box:
        return Box(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )


class TextBlock(BaseModel):
    """A piece of text in reading order: a PDF text block, a Word paragraph or table row."""

    text: str
    # 0-based page; null when the format has no fixed pages (Word).
    page: int | None = None
    # Where the text sits on the page (PDF only).
    box: Box | None = None
    # A section title (Word heading): starts a new passage and gives it its context.
    heading: bool = False


class ExtractedDocument(BaseModel):
    # Null when the format has no fixed pages (Word).
    pages: int | None
    blocks: list[TextBlock]


class UnreadableDocumentError(Exception):
    """The file cannot be opened, or holds no text (a scan, for instance).

    The message is shown to the user.
    """
