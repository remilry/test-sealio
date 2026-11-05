"""PDF parser on the real Annex 7, plus synthetic forms to check the detection stays generic."""

import pymupdf
import pytest

from app.core.config import get_settings
from app.modules.forms.parsing.pdf_parser import parse_pdf
from app.modules.forms.parsing.schema import FieldKind, FormSchema
from tests.modules.helpers import pdf_locator

ANNEX_7 = "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"

# Expected schema, written by hand from the rendered page (points, origin top-left):
# (key, label, kind, writable box rounded to the point, has dots to erase).
EXPECTED_ANNEX_7 = [
    (
        "project_number_project_title_project_name",
        "Project number/project title/project name",
        FieldKind.TEXT,
        (270, 209, 535, 219),
        True,
    ),
    (
        "name_of_the_contracting_authority",
        "Name of the contracting authority",
        FieldKind.TEXT,
        (238, 232, 535, 242),
        True,
    ),
    # Table cells: the answer goes to the right of the label, up to the cell's right rule.
    ("name_and_legal_form", "Name and legal form", FieldKind.TEXT, (190, 293, 533, 303), False),
    ("business_address", "Business address", FieldKind.TEXT, (176, 318, 533, 328), False),
    ("contact_person", "Contact person", FieldKind.TEXT, (165, 342, 533, 352), False),
    ("telephone", "Telephone", FieldKind.TEXT, (144, 367, 308, 377), False),
    ("e_mail", "E-mail", FieldKind.TEXT, (350, 367, 533, 377), False),
    # Dot leaders with the label on their left, as separate text.
    ("place_and_date", "Place and date", FieldKind.TEXT, (337, 650, 535, 660), True),
    (
        "first_name_s_and_surname_s",
        "First name(s) and surname(s)",
        FieldKind.TEXT,
        (337, 673, 535, 683),
        True,
    ),
    ("signature_s", "Signature(s)", FieldKind.SIGNATURE, (337, 697, 535, 707), True),
]


@pytest.fixture(scope="module")
def annex_7() -> FormSchema:
    return parse_pdf((get_settings().seed_forms_dir / ANNEX_7).read_bytes())


def test_annex_7_fields_match_the_expected_schema(annex_7: FormSchema) -> None:
    actual = [
        (
            field.key,
            field.label,
            field.kind,
            tuple(round(v) for v in pdf_locator(field).box.model_dump().values()),
            bool(pdf_locator(field).erase),
        )
        for field in annex_7.fields
    ]

    assert actual == EXPECTED_ANNEX_7


def test_annex_7_is_one_a4_page_and_one_section(annex_7: FormSchema) -> None:
    assert [(round(p.width), round(p.height)) for p in annex_7.pages] == [(595, 842)]
    assert {field.section for field in annex_7.fields} == {"Page 1"}
    assert {pdf_locator(field).page for field in annex_7.fields} == {0}


def test_answers_sit_on_the_label_line_at_the_label_size(annex_7: FormSchema) -> None:
    for field in annex_7.fields:
        box = pdf_locator(field).box
        assert box.y0 < pdf_locator(field).baseline <= box.y1
        assert pdf_locator(field).font_size == 10


def test_dots_to_erase_are_inside_the_writable_box(annex_7: FormSchema) -> None:
    for field in annex_7.fields:
        box = pdf_locator(field).box
        for mark in pdf_locator(field).erase:
            assert box.x0 <= mark.x0 < mark.x1 <= box.x1


def _pdf(draw) -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        draw(page)
        return doc.tobytes()


def _text(page: pymupdf.Page, point: tuple[float, float], text: str, size: float = 10) -> None:
    """Write Unicode text (`…` included) with an embedded font, like real forms do."""
    writer = pymupdf.TextWriter(page.rect)
    writer.append(point, text, font=pymupdf.Font("helv"), fontsize=size)  # pyright: ignore[reportArgumentType]
    writer.write_text(page)


def test_detects_dot_leaders_with_the_label_before_or_above() -> None:
    def draw(page: pymupdf.Page) -> None:
        _text(page, (72, 100), "Company name: ..........................", 11)
        _text(page, (72, 140), "Registered office", 11)
        _text(page, (72, 156), "……………………………………", 11)
        _text(page, (72, 200), "A sentence that simply ends with an ellipsis...", 11)

    schema = parse_pdf(_pdf(draw))

    assert [(f.label, f.kind) for f in schema.fields] == [
        ("Company name", FieldKind.TEXT),
        ("Registered office", FieldKind.TEXT),
    ]
    assert pdf_locator(schema.fields[0]).font_size == 11


def test_detects_an_empty_ruled_cell_but_not_a_filled_one() -> None:
    def draw(page: pymupdf.Page) -> None:
        for top in (100, 130):
            page.draw_rect(pymupdf.Rect(72, top, 520, top + 30), color=(0, 0, 0), width=0.5)
        _text(page, (76, 118), "VAT number", 10)
        _text(page, (76, 148), "Already written", 10)
        _text(page, (300, 148), "CHE-123.456.789", 10)

    schema = parse_pdf(_pdf(draw))

    [cell] = schema.fields
    assert cell.label == "VAT number"
    assert pdf_locator(cell).box.x1 < 520
    assert pdf_locator(cell).erase == []


def test_signature_and_stamp_blanks_are_signatures() -> None:
    def draw(page: pymupdf.Page) -> None:
        _text(page, (72, 100), "Company stamp ……………………", 10)
        _text(page, (72, 130), "Signature of the director ……………………", 10)

    schema = parse_pdf(_pdf(draw))

    assert [f.kind for f in schema.fields] == [FieldKind.SIGNATURE, FieldKind.SIGNATURE]


def test_duplicate_labels_get_unique_keys() -> None:
    def draw(page: pymupdf.Page) -> None:
        _text(page, (72, 100), "Name ……………………", 10)
        _text(page, (72, 130), "Name ……………………", 10)

    schema = parse_pdf(_pdf(draw))

    assert [f.key for f in schema.fields] == ["name", "name_2"]
