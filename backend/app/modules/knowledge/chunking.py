"""Text blocks → passages, the unit the search returns and the AI cites (pure).

A passage stays on one page (so its source can be shown in place) and within one section, and
holds a few blocks: enough context for the AI, small enough for the search to stay precise.
"""

from pydantic import BaseModel

from app.modules.knowledge.extraction.blocks import Box, TextBlock

MAX_CHARS = 800


class Passage(BaseModel):
    # The passage's text, verbatim: citations are checked against it.
    text: str
    # Document title and section heading: helps the search, never cited.
    context: str
    page: int | None
    box: Box | None


def chunk(
    document_title: str, blocks: list[TextBlock], max_chars: int = MAX_CHARS
) -> list[Passage]:
    passages: list[Passage] = []
    current: list[TextBlock] = []
    heading: str | None = None

    def flush() -> None:
        if current:
            passages.append(_passage(document_title, heading, current))
            current.clear()

    for block in blocks:
        if block.heading:
            flush()
            heading = block.text
            # The heading is part of the passage it opens.
        elif current and (
            block.page != current[0].page or _length(current) + len(block.text) > max_chars
        ):
            flush()
        current.append(block)
    flush()
    return passages


def _length(blocks: list[TextBlock]) -> int:
    return sum(len(block.text) + 1 for block in blocks)


def _passage(document_title: str, heading: str | None, blocks: list[TextBlock]) -> Passage:
    boxes = [block.box for block in blocks if block.box is not None]
    box = None
    for each in boxes:
        box = each if box is None else box.union(each)
    return Passage(
        text="\n".join(block.text for block in blocks),
        context=document_title if heading is None else f"{document_title} — {heading}",
        page=blocks[0].page,
        box=box,
    )
