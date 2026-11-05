"""Word form parser: one synthetic document per generic rule, then the real Annex 4."""

import io
from collections.abc import Callable

import pytest
from docx import Document
from docx.document import Document as DocumentObject
from docx.table import _Cell  # pyright: ignore[reportPrivateUsage]

from app.core.config import get_settings
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
                loc.start,
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
        ("Business purpose", TEXT, "Table 1", IN, 0, 0, 0, 0, 17),
        ("Main activity", TEXT, "Table 1", IN, 0, 0, 0, 1, 14),
        ("Secondary activities", TEXT, "Table 1", IN, 0, 0, 0, 2, 21),
    ]


def test_label_ending_with_colon_and_tab() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Legal form: \t"
        table.cell(0, 1).text = " Registered office:"

    assert _fields(_parse(build)) == [
        ("Legal form", TEXT, "Table 1", IN, 0, 0, 0, 0, 13),
        ("Registered office", TEXT, "Table 1", IN, 0, 0, 1, 0, 19),
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
        ("AHV compensation office (exact address)", TEXT, "Table 1", IN, 0, 0, 0, 0, 40),
        ("For foreign bidders", TEXT, "Table 1", NEW, 0, 0, 0, 1, None),
        ("BVG pension fund", TEXT, "Table 1", IN, 0, 1, 0, 0, 17),
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
        ("Tender (No. …, type of work)", TEXT, "Table 1", LEADER, 0, 0, 0, 2, 12),
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
        ("Place and date", TEXT, "Text", IN, None, None, None, 2, 16),
        (
            "Company stamp and legally valid signature(s)",
            SIGNATURE,
            "Text",
            IN,
            None,
            None,
            None,
            2,
            66,
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


def test_a_sentence_next_to_a_title_is_not_a_field() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=1, cols=2)
        _cell_paragraphs(table.cell(0, 0), ["Questionnaire for bidders", "", "Tender (No. ……)"])
        table.cell(0, 1).text = (
            "The information will be treated confidentially and used solely for the evaluation "
            "of this tender"
        )

    assert [label for label, *_ in _fields(_parse(build))] == ["Tender (No. …)"]


# --- The real Annex 4 ------------------------------------------------------------------------

ANNEX_4 = "Annex_4_Conditions of Participation and Company Self-Declaration.docx"


@pytest.fixture(scope="module")
def annex_4() -> FormSchema:
    return parse_docx((get_settings().seed_forms_dir / ANNEX_4).read_bytes())


def test_annex_4_fields(annex_4: FormSchema) -> None:
    assert [(f.key, f.kind, f.section, docx_locator(f).mode) for f in annex_4.fields] == [
        ("tender_no_type_of_work", TEXT, "Table 1", LEADER),
        ("exact_company_name", TEXT, "Table 2", IN),
        ("street_postcode_city_country", TEXT, "Table 2", IN),
        ("telephone_e_mail", TEXT, "Table 2", IN),
        ("responsible_person_contact_person", TEXT, "Table 2", IN),
        ("uid", TEXT, "Table 2", IN),
        ("legal_form", TEXT, "Table 3", IN),
        ("registered_office", TEXT, "Table 3", IN),
        ("company_has_had_this_legal_form_since", TEXT, "Table 3", IN),
        ("ownership_structure_incl_own_shareholdings", TEXT, "Table 3", IN),
        ("share_capital", TEXT, "Table 3", IN),
        ("business_purpose", TEXT, "Table 3", IN),
        ("main_activity", TEXT, "Table 3", IN),
        ("secondary_activities", TEXT, "Table 3", IN),
        ("certificates", TEXT, "Table 3", IN),
        ("with_higher_professional_training", TEXT, "Table 4", IN),
        ("with_professional_training", TEXT, "Table 4", NEW),
        ("auxiliary_staff", TEXT, "Table 4", NEW),
        ("apprentices", TEXT, "Table 4", NEW),
        ("insurance_coverage_details", TEXT, "Table 5", IN),
        ("insurance_company", TEXT, "Table 5", IN),
        ("personal_injury", TEXT, "Table 5", IN),
        ("property_damage", TEXT, "Table 5", IN),
        ("financial_loss", TEXT, "Table 5", IN),
        ("competent_tax_office_exact_address", TEXT, "Table 6", IN),
        ("ahv_compensation_office_exact_address", TEXT, "Table 6", IN),
        ("for_foreign_bidders_details_of_the_pension_scheme_exact_addr", TEXT, "Table 6", NEW),
        ("bvg_pension_fund_exact_address_and_details", TEXT, "Table 6", IN),
        ("for_foreign_bidders_details_of_the_pension_scheme_exact_addr_2", TEXT, "Table 6", IN),
        ("do_you_comply_with_the_applicable_occupational_health_and_sa", YES_NO, "Table 7", IN),
        ("do_you_comply_with_the_collective_employment_agreement_that_", YES_NO, "Table 7", IN),
        ("do_you_comply_with_the_standard_employment_contract_that_app", YES_NO, "Table 7", IN),
        ("do_you_comply_with_the_customary_wage_and_working_conditions", YES_NO, "Table 7", IN),
        ("only_for_services_to_be_performed_abroad_for_the_services_to", YES_NO, "Table 7", IN),
        ("do_you_comply_with_the_principle_of_non_discrimination_in_pa", YES_NO, "Table 7", IN),
        ("have_you_paid_in_full_the_taxes_due_at_your_place_of_busines", YES_NO, "Table 7", IN),
        ("have_you_paid_in_full_the_vat_or_sales_tax_due", YES_NO, "Table 7", IN),
        ("have_you_paid_in_full_the_social_security_contributions_due_", YES_NO, "Table 7", IN),
        ("have_you_paid_in_full_the_contributions_due_under_generally_", YES_NO, "Table 7", IN),
        ("are_you_subject_to_debt_enforcement_or_bankruptcy_proceeding", YES_NO, "Table 7", IN),
        ("have_any_seizures_been_carried_out_against_you_in_the_past_t", YES_NO, "Table 7", IN),
        ("have_you_entered_into_any_agreements_or_taken_other_measures", YES_NO, "Table 7", IN),
        ("do_you_confirm_that_you_are_not_on_the_list_of_sanctioned_bi", YES_NO, "Table 7", IN),
        ("do_you_comply_with_the_swiss_regulations_on_environmental_pr", YES_NO, "Table 7", IN),
        ("only_for_services_to_be_performed_abroad_do_you_comply_with_", YES_NO, "Table 7", IN),
        ("do_you_confirm_that_you_have_included_or_will_include_the_ab", YES_NO, "Table 7", IN),
        ("remarks", TEXT, "Table 7", IN),
        ("place_and_date", TEXT, "Text", IN),
        ("company_stamp_and_legally_valid_signature_s", SIGNATURE, "Text", IN),
    ]


def test_annex_4_labels_read_as_in_the_form(annex_4: FormSchema) -> None:
    labels = {f.key: f.label for f in annex_4.fields}

    assert labels["tender_no_type_of_work"] == "Tender (No. …, type of work)"
    assert labels["legal_form"] == "Legal form"
    assert labels["ownership_structure_incl_own_shareholdings"] == (
        "Ownership structure (incl. own shareholdings)"
    )
    assert labels["have_you_paid_in_full_the_vat_or_sales_tax_due"] == (
        "Have you paid in full the VAT or sales tax due?"
    )
    assert labels["company_stamp_and_legally_valid_signature_s"] == (
        "Company stamp and legally valid signature(s)"
    )


def test_annex_4_locators_are_distinct(annex_4: FormSchema) -> None:
    places = [
        (loc.table, loc.row, loc.cell, loc.paragraph, loc.mode, loc.start)
        for loc in map(docx_locator, annex_4.fields)
    ]

    assert len(places) == len(set(places))


def test_annex_4_counts(annex_4: FormSchema) -> None:
    kinds = [f.kind for f in annex_4.fields]

    assert len(kinds) == 49
    assert kinds.count(YES_NO) == 17
    assert kinds.count(SIGNATURE) == 1


def test_a_label_merged_over_two_rows_is_one_field() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).merge(table.cell(1, 0)).text = "Company"

    assert [(f.label, docx_locator(f).row, docx_locator(f).cell) for f in _parse(build).fields] == [
        ("Company", 0, 1)
    ]


def test_an_answer_cell_merged_over_two_rows_belongs_to_the_first_label() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Name"
        table.cell(1, 0).text = "City"
        table.cell(0, 1).merge(table.cell(1, 1))

    fields = {f.label: docx_locator(f) for f in _parse(build).fields}

    assert (fields["Name"].row, fields["Name"].cell, fields["Name"].mode) == (0, 1, IN)
    assert (fields["City"].row, fields["City"].cell, fields["City"].mode) == (1, 0, NEW)


def test_a_yes_no_question_is_the_longest_cell_before_the_answer() -> None:
    def build(document: DocumentObject) -> None:
        table = document.add_table(rows=2, cols=3)
        table.cell(0, 0).text = "No."
        table.cell(0, 1).text = "Question"
        table.cell(0, 2).text = "Answer: Yes/No"
        table.cell(1, 0).text = "1"
        table.cell(1, 1).text = "Do you comply with the occupational health and safety rules?"

    assert [(f.label, f.kind, docx_locator(f).cell) for f in _parse(build).fields] == [
        ("Do you comply with the occupational health and safety rules?", YES_NO, 2)
    ]
