"""Word form parser: one synthetic document per generic rule, then the real Annex 4."""

import io
from collections.abc import Callable

from docx import Document
from docx.document import Document as DocumentObject
from docx.table import _Cell  # pyright: ignore[reportPrivateUsage]

from app.modules.forms.parsing.docx_parser import parse_docx
from app.modules.forms.parsing.schema import DocxWriteMode, FieldKind, FormSchema
from tests.modules.helpers import docx_locator

IN, NEW, LEADER = (
    DocxWriteMode.IN_PARAGRAPH,
    DocxWriteMode.NEW_PARAGRAPH,
    DocxWriteMode.REPLACE_LEADER,
)
TEXT, YES_NO, SIGNATURE = FieldKind.TEXT, FieldKind.YES_NO, FieldKind.SIGNATURE
LONG = (
    "The information will be treated confidentially and used solely for the evaluation of the "
    "bids; bidders who fail to provide it will be excluded from the procedure."
)


def _parse(build: Callable[[DocumentObject], None]) -> FormSchema:
    document = Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return parse_docx(buffer.getvalue())


def _fields(schema: FormSchema) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for field in schema.fields:
        loc = docx_locator(field)
        rows.append(
            (
                field.label,
                field.kind,
                field.section,
                loc.mode,
                loc.table,
                loc.row,
                loc.cell,
                loc.paragraph,
                loc.after_run,
            )
        )
    return rows


def _cell_paragraphs(cell: _Cell, texts: list[str]) -> None:
    cell.text = texts[0]
    for text in texts[1:]:
        cell.add_paragraph(text)


def test_label_next_to_an_empty_cell() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Exact company name"
        table.cell(1, 0).text = "UID"

    assert _fields(_parse(build)) == [
        ("Exact company name", TEXT, "Table 1", IN, 0, 0, 1, 0, None),
        ("UID", TEXT, "Table 1", IN, 0, 1, 1, 0, None),
    ]


def test_label_above_an_empty_paragraph() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=1)
        _cell_paragraphs(table.cell(0, 0), ["Insurance company:", ""])

    assert _fields(_parse(build)) == [("Insurance company", TEXT, "Table 1", IN, 0, 0, 0, 1, None)]


def test_stacked_labels_with_colons() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=1)
        _cell_paragraphs(
            table.cell(0, 0), ["Business purpose:", "Main activity:", "Secondary activities:"]
        )

    assert _fields(_parse(build)) == [
        ("Business purpose", TEXT, "Table 1", IN, 0, 0, 0, 0, 0),
        ("Main activity", TEXT, "Table 1", IN, 0, 0, 0, 1, 0),
        ("Secondary activities", TEXT, "Table 1", IN, 0, 0, 0, 2, 0),
    ]


def test_label_ending_with_colon_and_tab() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Legal form: \t"
        table.cell(0, 1).text = " Registered office:"

    assert _fields(_parse(build)) == [
        ("Legal form", TEXT, "Table 1", IN, 0, 0, 0, 0, 0),
        ("Registered office", TEXT, "Table 1", IN, 0, 0, 1, 0, 0),
    ]


def test_short_labels_alone_in_their_cells_under_a_heading() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=3)
        heading = table.cell(0, 0).merge(table.cell(0, 2))
        heading.text = "Number of employees in the area essential to performing the contract"
        _cell_paragraphs(table.cell(1, 0), ["With higher professional training", ""])
        table.cell(1, 1).text = "With professional training"
        table.cell(1, 2).text = "Apprentices"

    assert _fields(_parse(build)) == [
        ("With higher professional training", TEXT, "Table 1", IN, 0, 1, 0, 1, None),
        ("With professional training", TEXT, "Table 1", NEW, 0, 1, 1, 0, None),
        ("Apprentices", TEXT, "Table 1", NEW, 0, 1, 2, 0, None),
    ]


def test_a_label_heading_several_labels_on_its_right_is_not_a_field() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Available amounts per claim:"
        _cell_paragraphs(table.cell(0, 1), ["Personal injury:", "Property damage:"])

    assert [label for label, *_ in _fields(_parse(build))] == ["Personal injury", "Property damage"]


def test_labels_after_an_address_label_in_the_same_cell() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=1)
        _cell_paragraphs(
            table.cell(0, 0), ["AHV compensation office (exact address):", "For foreign bidders"]
        )
        _cell_paragraphs(table.cell(1, 0), ["BVG pension fund:", "For foreign bidders", ""])

    schema = _parse(build)

    assert _fields(schema) == [
        ("AHV compensation office (exact address)", TEXT, "Table 1", IN, 0, 0, 0, 0, 0),
        ("For foreign bidders", TEXT, "Table 1", NEW, 0, 0, 0, 1, None),
        ("BVG pension fund", TEXT, "Table 1", IN, 0, 1, 0, 0, 0),
        ("For foreign bidders", TEXT, "Table 1", IN, 0, 1, 0, 2, None),
    ]
    assert [f.key for f in schema.fields] == [
        "ahv_compensation_office_exact_address",
        "for_foreign_bidders",
        "bvg_pension_fund",
        "for_foreign_bidders_2",
    ]


def test_yes_no_table() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=4, cols=2)
        _cell_paragraphs(table.cell(0, 0), ["Self-declaration", "(Please answer with Yes or No):"])
        _cell_paragraphs(table.cell(0, 1), ["", "Answer: Yes/No"])
        table.cell(1, 0).text = "Do you comply with the occupational health and safety rules?"
        _cell_paragraphs(table.cell(2, 0), ["Only for services abroad", "Do you comply with ILO?"])
        remarks = table.cell(3, 0).merge(table.cell(3, 1))
        _cell_paragraphs(remarks, ["Remarks:", "", ""])

    assert _fields(_parse(build)) == [
        (
            "Do you comply with the occupational health and safety rules?",
            YES_NO,
            "Table 1",
            IN,
            0,
            1,
            1,
            0,
            None,
        ),
        (
            "Only for services abroad Do you comply with ILO?",
            YES_NO,
            "Table 1",
            IN,
            0,
            2,
            1,
            0,
            None,
        ),
        ("Remarks", TEXT, "Table 1", IN, 0, 3, 0, 1, None),
    ]


def test_dot_leader_in_a_paragraph() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=1)
        _cell_paragraphs(
            table.cell(0, 0),
            ["Questionnaire for bidders", "", "Tender (No. ………., type of work)", ""],
        )

    assert _fields(_parse(build)) == [
        ("Tender (No. …, type of work)", TEXT, "Table 1", LEADER, 0, 0, 0, 2, 0),
    ]


def test_place_and_date_and_signature_outside_tables() -> None:
    def build(document: DocumentObject) -> None:
        document.add_paragraph("Mandatory additional evidence for the assessment of suitability:")
        document.add_paragraph("Commercial register extract no older than 3 months")
        paragraph = document.add_paragraph()
        paragraph.add_run("Place and date: ")
        paragraph.add_run("\t\t\t\t\t")
        paragraph.add_run("Company stamp and legally valid signature(s):")
        document.add_paragraph("______________________________")

    assert _fields(_parse(build)) == [
        ("Place and date", TEXT, "Text", IN, None, None, None, 2, 0),
        (
            "Company stamp and legally valid signature(s)",
            SIGNATURE,
            "Text",
            IN,
            None,
            None,
            None,
            2,
            2,
        ),
    ]


def test_explanations_and_headings_are_not_fields() -> None:
    def build(document: DocumentObject) -> None:
        document.add_paragraph(LONG)
        table = document.add_table(rows=2, cols=2)
        _cell_paragraphs(table.cell(0, 0), [LONG, ""])
        heading = table.cell(1, 0).merge(table.cell(1, 1))
        heading.text = "General information about the company"
        document.add_paragraph("Conditions of Participation and Company Self-Declaration")

    assert _parse(build).fields == []


def test_sections_follow_the_tables() -> None:
    def build(document: DocumentObject) -> None:
        document.add_table(rows=1, cols=2).cell(0, 0).text = "UID"
        document.add_paragraph("Between the tables.")
        document.add_table(rows=1, cols=2).cell(0, 0).text = "Share capital"

    assert [(f.section, docx_locator(f).table) for f in _parse(build).fields] == [
        ("Table 1", 0),
        ("Table 2", 1),
    ]
