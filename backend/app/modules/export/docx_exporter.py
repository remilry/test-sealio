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
from app.modules.forms.parsing.labels import leader_runs
from app.modules.forms.parsing.schema import DocxLocator, DocxWriteMode

DOCUMENT_PART = "word/document.xml"
# Word's own defaults, when the document does not say.
DEFAULT_TAB_STOP_PT = 36.0
DEFAULT_FONT_SIZE_PT = 10.0
# Average glyph width as a share of the font size, to estimate how far a value reaches.
CHAR_WIDTH_EM = 0.5
# Properties of a paragraph mark that are not run formatting (revision marks).
NOT_RUN_FORMATTING = {qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo")}


def export_docx(original: bytes, answers: list[tuple[DocxLocator, str]]) -> bytes:
    to_write = [(locator, _one_line(value)) for locator, value in answers if value.strip()]
    if not to_write:
        return original
    document = Document(io.BytesIO(original))
    # Every paragraph is found before any is changed: a new paragraph shifts the next indexes.
    targets = [(paragraph_at(document, locator), locator, value) for locator, value in to_write]
    tab_stop = _default_tab_stop(document)
    for paragraph, locator, value in targets:
        _write(paragraph, locator, value, tab_stop)
    return _replace_part(original, DOCUMENT_PART, _serialize(document))


def _one_line(value: str) -> str:
    text = " ".join(value.split())
    # Yes/No answers are written in full, capitalised.
    return text.capitalize() if text.lower() in ("yes", "no") else text


def _write(paragraph: Paragraph, locator: DocxLocator, value: str, tab_stop: float) -> None:
    runs = paragraph.runs
    match locator.mode:
        case DocxWriteMode.REPLACE_LEADER:
            _replace_leader(paragraph, locator.after_run or 0, value)
        case DocxWriteMode.NEW_PARAGRAPH:
            new = copy.deepcopy(paragraph._p)  # pyright: ignore[reportPrivateUsage]
            for child in list(new):
                if child.tag != qn("w:pPr"):
                    new.remove(child)
            label_run = runs[-1]._r if runs else None  # pyright: ignore[reportPrivateUsage]
            new.append(_run(value, _run_properties(label_run, paragraph)))
            paragraph._p.addnext(new)  # pyright: ignore[reportPrivateUsage]
        case DocxWriteMode.IN_PARAGRAPH if locator.after_run is None:
            label_run = runs[-1]._r if runs else None  # pyright: ignore[reportPrivateUsage]
            paragraph._p.append(_run(value, _run_properties(label_run, paragraph)))  # pyright: ignore[reportPrivateUsage]
        case DocxWriteMode.IN_PARAGRAPH:
            index = locator.after_run
            assert index is not None
            label = runs[index]._r  # pyright: ignore[reportPrivateUsage]
            before = "".join(run.text for run in runs[: index + 1])
            text = value if before[-1:].isspace() else f" {value}"
            properties = _run_properties(label, paragraph)
            label.addnext(_run(text, properties))
            _absorb_tabs(runs[index + 1 :], text, _font_size(properties), tab_stop)


def _replace_leader(paragraph: Paragraph, index: int, value: str) -> None:
    runs = paragraph.runs
    run = runs[index]
    spans = leader_runs(run.text)
    if spans:
        start, end = spans[0]
        run.text = run.text[:start] + value + run.text[end:]
    # A leader split over the next runs: their dots go too.
    for following in runs[index + 1 :]:
        stripped = following.text.lstrip("….")
        if stripped == following.text:
            break
        following.text = stripped


def _absorb_tabs(following: list[Run], value: str, size: float, tab_stop: float) -> None:
    """When tabs separate the label from more text on its line, drop as many as the value takes
    (at least one kept), so the text after them stays where it was."""
    tab_runs: list[Run] = []
    for run in following:
        if run.text and not run.text.strip():
            tab_runs.append(run)
            continue
        if not run.text.strip():
            continue
        break
    else:
        return  # nothing after the tabs: they can stay
    tabs = [tab for run in tab_runs for tab in run._r.findall(qn("w:tab"))]  # pyright: ignore[reportPrivateUsage]
    width = len(value) * size * CHAR_WIDTH_EM
    for tab in tabs[: min(math.ceil(width / tab_stop), len(tabs) - 1)]:
        tab.getparent().remove(tab)


def _run(text: str, properties: BaseOxmlElement | None) -> BaseOxmlElement:
    run = OxmlElement("w:r")
    if properties is not None:
        run.append(properties)
    t = OxmlElement("w:t")
    run.append(t)
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return run


def _run_properties(
    label_run: BaseOxmlElement | None, paragraph: Paragraph
) -> BaseOxmlElement | None:
    """A copy of the label run's formatting, or of the paragraph mark's for an empty paragraph."""
    if label_run is not None:
        source = label_run.find(qn("w:rPr"))
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
