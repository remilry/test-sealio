"""Write answers into the original Word form. Pure: bytes in, bytes out.

Each value goes where the parser located it (`DocxLocator`), in a new run that copies the label's
formatting. Only `word/document.xml` is rewritten; every other part of the package (styles,
numbering, headers, images…) is copied byte for byte. The caller leaves out signatures.
"""

import copy
import io
import math
import zipfile

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.modules.forms.parsing.docx_layout import paragraph_at
from app.modules.forms.parsing.schema import DocxLocator, DocxWriteMode

DOCUMENT_PART = "word/document.xml"
# Word's own defaults, when the document does not say.
DEFAULT_TAB_STOP_PT = 36.0
DEFAULT_FONT_SIZE_PT = 10.0
# Average glyph width as a share of the font size, to estimate how far a value reaches.
CHAR_WIDTH_EM = 0.5
# Properties of a paragraph mark that are not run formatting (revision marks).
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NOT_RUN_FORMATTING = {qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo")}


def export_docx(original: bytes, answers: list[tuple[DocxLocator, str]]) -> bytes:
    to_write = [(locator, _one_line(value)) for locator, value in answers if value.strip()]
    if not to_write:
        return original
    document = Document(io.BytesIO(original))
    # Every paragraph is found before any is changed (a new paragraph shifts the next indexes),
    # and a paragraph is written from its end: the offsets before a write stay valid.
    targets = [(paragraph_at(document, locator), locator, value) for locator, value in to_write]
    targets.sort(key=lambda target: -_offset(target[0], target[1]))
    tab_stop = _default_tab_stop(document)
    for paragraph, locator, value in targets:
        _write(paragraph, locator, value, tab_stop)
    return _replace_part(original, DOCUMENT_PART, _serialize(document))


def _one_line(value: str) -> str:
    text = " ".join(value.split())
    # Yes/No answers are written in full, capitalised.
    return text.capitalize() if text.lower() in ("yes", "no") else text


def _text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _offset(paragraph: Paragraph, locator: DocxLocator) -> int:
    """Where the value goes in the paragraph's text (its end when the locator gives none)."""
    return len(_text(paragraph)) if locator.start is None else locator.start


def _write(paragraph: Paragraph, locator: DocxLocator, value: str, tab_stop: float) -> None:
    if locator.mode == DocxWriteMode.NEW_PARAGRAPH:
        new = copy.deepcopy(paragraph._p)  # pyright: ignore[reportPrivateUsage]
        for child in list(new):
            if child.tag != qn("w:pPr"):
                new.remove(child)
        runs = paragraph.runs
        new.append(_run(value, _run_properties(runs[-1] if runs else None, paragraph)))
        paragraph._p.addnext(new)  # pyright: ignore[reportPrivateUsage]
        return
    text = _text(paragraph)
    start = _offset(paragraph, locator)
    if locator.mode == DocxWriteMode.REPLACE_LEADER:
        end = locator.end if locator.end is not None else start
        _replace(paragraph, start, end, value)
        return
    before = text[:start]
    written = f" {value}" if before and not before[-1].isspace() else value
    _insert(paragraph, start, written)
    _absorb_tabs(paragraph, start + len(written), text[start:], written, tab_stop)


# --- Runs, cut at character offsets ---------------------------------------------------------

CONTENT = ("w:t", "w:tab", "w:br", "w:cr", "w:noBreakHyphen", "w:ptab")


def _content(run: BaseOxmlElement) -> list[BaseOxmlElement]:
    """The run's children that make its text, in order (`Run.text` counts the same ones)."""
    tags = {qn(tag) for tag in CONTENT}
    return [child for child in run if child.tag in tags]


def _cut(paragraph: Paragraph, offset: int) -> int:
    """Split the run that spans `offset`, so a run starts there. Returns that run's index
    (the number of runs when offset is the end of the paragraph)."""
    position = 0
    for index, run in enumerate(paragraph.runs):
        length = len(run.text)
        if offset <= position:
            return index
        if offset < position + length:
            _split_run(run._r, offset - position)  # pyright: ignore[reportPrivateUsage]
            return index + 1
        position += length
    return len(paragraph.runs)


def _split_run(run: BaseOxmlElement, at: int) -> None:
    """Split a run after its first `at` characters: the rest goes into a copy placed after it."""
    rest = copy.deepcopy(run)
    position = 0
    for kept, moved in zip(_content(run), _content(rest), strict=True):
        length = len(str(kept))
        if position + length <= at:
            rest.remove(moved)
        elif position >= at:
            run.remove(kept)
        else:  # a w:t straddling the cut
            cut = at - position
            moved.text, kept.text = (kept.text or "")[cut:], (kept.text or "")[:cut]
            for part in (kept, moved):
                part.set(XML_SPACE, "preserve")
        position += length
    run.addnext(rest)


def _insert(paragraph: Paragraph, offset: int, value: str) -> None:
    index = _cut(paragraph, offset)
    runs = paragraph.runs
    # The text before the value gives its formatting (the label), else the text after it.
    neighbour = runs[index - 1] if index > 0 else (runs[index] if runs else None)
    new = _run(value, _run_properties(neighbour, paragraph))
    if index > 0:
        runs[index - 1]._r.addnext(new)  # pyright: ignore[reportPrivateUsage]
    elif runs:
        runs[0]._r.addprevious(new)  # pyright: ignore[reportPrivateUsage]
    else:
        paragraph._p.append(new)  # pyright: ignore[reportPrivateUsage]


def _replace(paragraph: Paragraph, start: int, end: int, value: str) -> None:
    """Characters [start, end) become the value, in the formatting of the first one."""
    # Cut at the start first: a cut after it never moves the run that starts there.
    first = _cut(paragraph, start)
    last = _cut(paragraph, end)
    covered = paragraph.runs[first:last]
    if not covered:
        _insert(paragraph, start, value)
        return
    head = covered[0]._r  # pyright: ignore[reportPrivateUsage]
    for child in _content(head):
        head.remove(child)
    text = OxmlElement("w:t")
    text.text = value
    text.set(XML_SPACE, "preserve")
    head.append(text)
    for run in covered[1:]:
        run._r.getparent().remove(run._r)  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]


def _absorb_tabs(paragraph: Paragraph, after: int, rest: str, value: str, tab_stop: float) -> None:
    """When tabs separate the value from more text on its line, drop as many as the value takes
    (at least one kept), so the text after them stays where it was."""
    gap = len(rest) - len(rest.lstrip(" \t"))
    if not rest[gap:].strip() or "\t" not in rest[:gap]:
        return
    tabs: list[BaseOxmlElement] = []
    position = 0
    for run in paragraph.runs:
        for child in _content(run._r):  # pyright: ignore[reportPrivateUsage]
            if after <= position < after + gap and child.tag == qn("w:tab"):
                tabs.append(child)
            position += len(str(child))
    size = _font_size(_run_properties(_run_before(paragraph, after), paragraph))
    width = len(value) * size * CHAR_WIDTH_EM
    for tab in tabs[: min(math.ceil(width / tab_stop), len(tabs) - 1)]:
        tab.getparent().remove(tab)  # pyright: ignore[reportOptionalMemberAccess]


def _run_before(paragraph: Paragraph, offset: int) -> Run | None:
    position = 0
    found = None
    for run in paragraph.runs:
        if position >= offset:
            break
        found = run
        position += len(run.text)
    return found


def _run(text: str, properties: BaseOxmlElement | None) -> BaseOxmlElement:
    run = OxmlElement("w:r")
    if properties is not None:
        run.append(properties)
    t = OxmlElement("w:t")
    run.append(t)
    t.text = text
    t.set(XML_SPACE, "preserve")
    return run


def _run_properties(run: Run | None, paragraph: Paragraph) -> BaseOxmlElement | None:
    """A copy of the run's formatting, or of the paragraph mark's for an empty paragraph."""
    if run is not None:
        source = run._r.rPr  # pyright: ignore[reportPrivateUsage]
        return None if source is None else copy.deepcopy(source)
    p_pr = paragraph._p.pPr  # pyright: ignore[reportPrivateUsage]
    mark = None if p_pr is None else p_pr.find(qn("w:rPr"))
    if mark is None:
        return None
    properties = OxmlElement("w:rPr")
    for child in mark:
        if child.tag not in NOT_RUN_FORMATTING:
            properties.append(copy.deepcopy(child))
    return properties


def _font_size(properties: BaseOxmlElement | None) -> float:  # pyright: ignore[reportPrivateUsage]
    size = None if properties is None else properties.find(qn("w:sz"))
    if size is None:
        return DEFAULT_FONT_SIZE_PT
    return int(size.get(qn("w:val"), "20")) / 2


def _default_tab_stop(document: DocumentObject) -> float:
    stop = document.settings.element.find(qn("w:defaultTabStop"))
    if stop is None:
        return DEFAULT_TAB_STOP_PT
    return int(stop.get(qn("w:val"), "720")) / 20  # twips → points


def _serialize(document: DocumentObject) -> bytes:
    return document.part.blob


def _replace_part(original: bytes, name: str, content: bytes) -> bytes:
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original)) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for info in source.infolist():
            target.writestr(info, content if info.filename == name else source.read(info.filename))
    return output.getvalue()
