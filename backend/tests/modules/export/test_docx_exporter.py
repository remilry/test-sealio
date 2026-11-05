"""Word export on the real Annex 4: answers where the parser located them, the rest unchanged."""

import io
import zipfile
from collections.abc import Callable

import pytest
from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.text.paragraph import Paragraph

from app.core.config import get_settings
from app.modules.export.docx_exporter import export_docx
from app.modules.forms.parsing.docx_layout import distinct_cells, paragraph_at
from app.modules.forms.parsing.docx_parser import parse_docx
from app.modules.forms.parsing.schema import DocxLocator, DocxWriteMode, FormSchema
from tests.modules.helpers import docx_locator

ANNEX_4 = "Annex_4_Conditions of Participation and Company Self-Declaration.docx"
LABEL_FONT = "HelveticaNeueLT Com 55 Roman"
VAT = "have_you_paid_in_full_the_vat_or_sales_tax_due"
HEALTH = "do_you_comply_with_the_applicable_occupational_health_and_sa"

VALUES = {
    "tender_no_type_of_work": "ZH-2026-0412, cloud platform services",  # replaces the dots
    "exact_company_name": "Alpenlogic AG",  # empty cell
    "legal_form": "Company limited by shares (AG)",  # after "Legal form: <tab>"
    "main_activity": "Digital transformation consulting",  # after a stacked label
    "insurance_company": "Limmat Versicherungen AG",  # empty paragraph below the label
    "with_higher_professional_training": "14",  # empty paragraph below the label
    "with_professional_training": "9",  # new paragraph below the label
    HEALTH: "yes",
    VAT: "No",
    "remarks": "None.",
    "place_and_date": "Zurich, 05.11.2026",  # before the tabs and the signature label
}


@pytest.fixture(scope="module")
def original() -> bytes:
    return (get_settings().seed_forms_dir / ANNEX_4).read_bytes()


@pytest.fixture(scope="module")
def schema(original: bytes) -> FormSchema:
    return parse_docx(original)


@pytest.fixture(scope="module")
def locators(schema: FormSchema) -> dict[str, DocxLocator]:
    return {field.key: docx_locator(field) for field in schema.fields}


@pytest.fixture(scope="module")
def exported(original: bytes, locators: dict[str, DocxLocator]) -> DocumentObject:
    answers = [(locators[key], value) for key, value in VALUES.items()]
    return Document(io.BytesIO(export_docx(original, answers)))


@pytest.fixture(scope="module")
def source(original: bytes) -> DocumentObject:
    return Document(io.BytesIO(original))


def _written(document: DocumentObject, locator: DocxLocator) -> Paragraph:
    """The paragraph that holds the field's value."""
    paragraph = paragraph_at(document, locator)
    if locator.mode == DocxWriteMode.NEW_PARAGRAPH:
        return Paragraph(paragraph._p.getnext(), paragraph._parent)  # pyright: ignore[reportPrivateUsage]
    return paragraph


def test_each_value_is_written_where_its_locator_points(
    exported: DocumentObject, locators: dict[str, DocxLocator]
) -> None:
    text = {key: _written(exported, locators[key]).text for key in VALUES}

    assert text["tender_no_type_of_work"] == (
        "Tender (No. ZH-2026-0412, cloud platform services, type of work)"
    )
    assert text["exact_company_name"] == "Alpenlogic AG"
    assert text["legal_form"] == "Legal form: \tCompany limited by shares (AG)"
    assert text["main_activity"] == "Main activity: Digital transformation consulting"
    assert text["insurance_company"] == "Limmat Versicherungen AG"
    assert text["with_higher_professional_training"] == "14"
    assert text["with_professional_training"] == "9"
    assert text["remarks"] == "None."
    assert text["place_and_date"].startswith("Place and date: Zurich, 05.11.2026\t")
    # The label of a new paragraph's field is left as it was.
    assert paragraph_at(exported, locators["with_professional_training"]).text == (
        "With professional training"
    )


def test_a_written_value_uses_the_label_font(
    exported: DocumentObject, locators: dict[str, DocxLocator]
) -> None:
    for key, value in VALUES.items():
        if key in (HEALTH, VAT, "tender_no_type_of_work"):
            continue  # written as Yes / No; in the dots' own run, with their formatting
        runs = [run for run in _written(exported, locators[key]).runs if value in run.text]
        assert runs, key
        assert runs[-1].font.name == LABEL_FONT, key
        size = runs[-1].font.size
        assert size is not None, key
        assert size.pt == 10, key


def test_yes_no_is_written_in_full(
    exported: DocumentObject, locators: dict[str, DocxLocator]
) -> None:
    assert _written(exported, locators[HEALTH]).text == "Yes"
    assert _written(exported, locators[VAT]).text == "No"


def test_tabs_absorb_the_place_and_date(
    exported: DocumentObject, source: DocumentObject, locators: dict[str, DocxLocator]
) -> None:
    before = paragraph_at(source, locators["place_and_date"]).text
    after = paragraph_at(exported, locators["place_and_date"]).text

    assert before.count("\t") == 5
    assert 1 <= after.count("\t") < 5
    assert after.endswith("Company stamp and legally valid signature(s):")


def test_values_are_written_on_one_line(original: bytes, locators: dict[str, DocxLocator]) -> None:
    locator = locators["street_postcode_city_country"]
    data = export_docx(original, [(locator, "  Pfingstweidstrasse 31\n8005 Zurich ")])

    assert paragraph_at(Document(io.BytesIO(data)), locator).text == (
        "Pfingstweidstrasse 31 8005 Zurich"
    )


def test_blank_values_leave_the_file_unchanged(
    original: bytes, locators: dict[str, DocxLocator]
) -> None:
    # (Signatures are never passed: the export service leaves them out, as for PDF.)
    assert export_docx(original, [(locator, "  ") for locator in locators.values()]) == original


def test_nothing_else_changes(
    original: bytes,
    exported: DocumentObject,
    source: DocumentObject,
    locators: dict[str, DocxLocator],
) -> None:
    data = export_docx(original, [(locators[key], value) for key, value in VALUES.items()])
    with (
        zipfile.ZipFile(io.BytesIO(original)) as before,
        zipfile.ZipFile(io.BytesIO(data)) as after,
    ):
        assert before.namelist() == after.namelist()
        for name in before.namelist():
            if name != "word/document.xml":
                assert before.read(name) == after.read(name), name

    filled = {_place(locators[key]) for key in VALUES}
    assert _untouched(source, filled) == _untouched(exported, filled)


def _place(locator: DocxLocator) -> tuple[int | None, int | None, int | None, int]:
    return (locator.table, locator.row, locator.cell, locator.paragraph)


def _xml(element: BaseOxmlElement | None) -> str:
    return "" if element is None else element.xml


def _untouched(
    document: DocumentObject, filled: set[tuple[int | None, int | None, int | None, int]]
) -> list[str]:
    """XML of every paragraph not addressed by a filled field (in a cell: the paragraphs before the
    first filled one, a new paragraph shifting the rest), plus every table, row and cell property
    and the section properties."""
    parts: list[str] = []
    for index, paragraph in enumerate(document.paragraphs):
        if (None, None, None, index) not in filled:
            parts.append(_xml(paragraph._p))  # pyright: ignore[reportPrivateUsage]
    for t, table in enumerate(document.tables):
        parts.append(_xml(table._tbl.tblPr))  # pyright: ignore[reportPrivateUsage]
        for r, row in enumerate(table.rows):
            if row._tr.trPr is not None:  # pyright: ignore[reportPrivateUsage]
                parts.append(_xml(row._tr.trPr))  # pyright: ignore[reportPrivateUsage]
            for c, cell in enumerate(distinct_cells(row)):
                parts.append(_xml(cell._tc.tcPr))  # pyright: ignore[reportPrivateUsage]
                touched = [p for (ft, fr, fc, p) in filled if (ft, fr, fc) == (t, r, c)]
                stop = min(touched) if touched else len(cell.paragraphs)
                parts.extend(_xml(p._p) for p in cell.paragraphs[:stop])  # pyright: ignore[reportPrivateUsage]
    parts.append(_xml(document.sections[-1]._sectPr))  # pyright: ignore[reportPrivateUsage]
    return parts


# --- Word structures other than Annex 4 ------------------------------------------------------

PLACE = "Zurich, 05.11.2026"


def _build(build: Callable[[DocumentObject], None]) -> bytes:
    document = Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _export(original: bytes, values: dict[str, str]) -> DocumentObject:
    fields = {field.label: docx_locator(field) for field in parse_docx(original).fields}
    answers = [(fields[label], value) for label, value in values.items()]
    return Document(io.BytesIO(export_docx(original, answers)))


def _body_line(*runs: str) -> bytes:
    def build(document: DocumentObject) -> None:
        paragraph = document.add_paragraph()
        for text in runs:
            paragraph.add_run(text)

    return _build(build)


def test_two_fields_in_one_paragraph_each_follow_their_label() -> None:
    original = _body_line("Name:", "\t\t", "City:", "\t\t")

    text = _export(original, {"Name": "Alpenlogic AG", "City": "Zurich"}).paragraphs[0].text

    assert text.startswith("Name: Alpenlogic AG\t")
    assert text.index("Zurich") > text.index("City:")


def test_label_tabs_and_trailing_text_in_one_run() -> None:
    original = _body_line("Place and date:\t\t\t\tCompany stamp and signature:")

    text = _export(original, {"Place and date": PLACE}).paragraphs[0].text

    assert text.startswith(f"Place and date: {PLACE}\t")
    assert 1 <= text.count("\t") < 4
    assert text.endswith("\tCompany stamp and signature:")


def test_label_and_tabs_in_one_run_trailing_text_in_the_next() -> None:
    original = _body_line("Place and date:\t\t\t\t", "Company stamp and signature:")

    text = _export(original, {"Place and date": PLACE}).paragraphs[0].text

    assert text.startswith(f"Place and date: {PLACE}\t")
    assert 1 <= text.count("\t") < 4
    assert text.endswith("\tCompany stamp and signature:")


def test_tabs_and_trailing_text_in_one_run() -> None:
    original = _body_line("Place and date: ", "\t\t\t\tCompany stamp and signature:")

    text = _export(original, {"Place and date": PLACE}).paragraphs[0].text

    assert text.startswith(f"Place and date: {PLACE}\t")
    assert 1 <= text.count("\t") < 4


def test_a_dot_leader_split_over_two_runs_is_replaced_whole() -> None:
    original = _body_line("Tender no. ...", "......... type of work")

    exported = _export(original, {"Tender no. … type of work": "ZH-2026-0412"})

    assert exported.paragraphs[0].text == "Tender no. ZH-2026-0412 type of work"


def test_an_answer_cell_merged_over_two_rows_gets_one_value() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Name"
        table.cell(1, 0).text = "City"
        table.cell(0, 1).merge(table.cell(1, 1))

    exported = _export(_build(build), {"Name": "Alpenlogic AG", "City": "Zurich"})

    table = exported.tables[0]
    assert table.cell(0, 1).text == "Alpenlogic AG"
    assert [p.text for p in table.cell(1, 0).paragraphs] == ["City", "Zurich"]
