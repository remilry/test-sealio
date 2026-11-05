"""PDF export on the real Annex 7: answers at the right place, everything else unchanged."""

import pymupdf
import pytest

from app.core.config import get_settings
from app.modules.export.pdf_exporter import MIN_FONT_SIZE, export_pdf, fitting_font_size
from app.modules.forms.parsing.pdf_parser import parse_pdf
from app.modules.forms.parsing.schema import Box, FormSchema, PdfLocator
from tests.modules.helpers import pdf_locator

ANNEX_7 = "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"
DOTS = set("….")

VALUES = {
    "project_number_project_title_project_name": "ZH-2026-0412 Cloud Platform Services",
    "name_and_legal_form": "Alpenlogic AG, Aktiengesellschaft",
    "telephone": "+41 44 512 38 00",
    "e_mail": "tenders@alpenlogic.ch",
    "place_and_date": "Zürich, 03.11.2026",
}


@pytest.fixture(scope="module")
def original() -> bytes:
    return (get_settings().seed_forms_dir / ANNEX_7).read_bytes()


@pytest.fixture(scope="module")
def schema(original: bytes) -> FormSchema:
    return parse_pdf(original)


@pytest.fixture(scope="module")
def exported(original: bytes, schema: FormSchema) -> bytes:
    answers = [(pdf_locator(f), VALUES[f.key]) for f in schema.fields if f.key in VALUES]
    return export_pdf(original, answers)


def _words(data: bytes) -> list[tuple[pymupdf.Rect, str]]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [(pymupdf.Rect(w[:4]), w[4]) for w in doc[0].get_text("words")]


def _inside(rect: pymupdf.Rect, box: Box) -> bool:
    return (
        box.x0 - 0.5 <= rect.x0
        and rect.x1 <= box.x1 + 0.5
        and box.y0 - 4 <= rect.y0  # the font ascender reaches above the label line
        and rect.y1 <= box.y1 + 2
    )


def test_each_value_is_written_inside_its_field_box(exported: bytes, schema: FormSchema) -> None:
    words = _words(exported)

    for field in schema.fields:
        if field.key not in VALUES:
            continue
        written = [text for rect, text in words if _inside(rect, pdf_locator(field).box)]
        assert " ".join(written) == VALUES[field.key], field.key


def test_dots_of_filled_fields_are_removed_and_kept_for_empty_ones(
    exported: bytes, schema: FormSchema
) -> None:
    words = _words(exported)

    for field in schema.fields:
        for mark in pdf_locator(field).erase:
            dots = [t for r, t in words if set(t) <= DOTS and _inside(r, mark)]
            assert bool(dots) == (field.key not in VALUES), field.key


def test_the_rest_of_the_page_is_unchanged(original: bytes, exported: bytes) -> None:
    value_words = {w for value in VALUES.values() for w in value.split()}

    before = [t for _, t in _words(original) if not set(t) <= DOTS and not t.endswith("…")]
    after = [t for _, t in _words(exported) if t not in value_words and not set(t) <= DOTS]

    # Labels such as "name:" keep their text; only the dot runs and the answers differ.
    assert [t.rstrip("….") for t in after] == [t.rstrip("….") for t in before]
    with (
        pymupdf.open(stream=original, filetype="pdf") as a,
        pymupdf.open(stream=exported, filetype="pdf") as b,
    ):
        assert b.page_count == a.page_count
        assert b[0].rect == a[0].rect
        assert len(b[0].get_images()) == len(a[0].get_images())
        assert len(b[0].get_drawings()) == len(a[0].get_drawings())


def test_no_answers_gives_back_the_same_content(original: bytes, schema: FormSchema) -> None:
    exported = export_pdf(original, [(pdf_locator(f), "  ") for f in schema.fields])

    assert [t for _, t in _words(exported)] == [t for _, t in _words(original)]


def test_a_long_value_is_shrunk_to_fit_its_box(original: bytes, schema: FormSchema) -> None:
    telephone = next(f for f in schema.fields if f.key == "telephone")
    value = "+41 44 512 38 00 (switchboard) or +41 79 123 45 67 (mobile)"

    words = _words(export_pdf(original, [(pdf_locator(telephone), value)]))

    written = [(r, t) for r, t in words if t in value.split() and r.y0 > 360 and r.y1 < 380]
    assert " ".join(t for _, t in written) == value
    assert max(r.x1 for r, _ in written) <= pdf_locator(telephone).box.x1 + 0.5


def test_font_size_keeps_the_preferred_size_when_it_fits_and_has_a_floor() -> None:
    assert fitting_font_size("short", 200, 10) == 10
    assert 5 < fitting_font_size("a" * 60, 200, 10) < 10
    assert fitting_font_size("a" * 1000, 50, 10) == MIN_FONT_SIZE


def test_unicode_values_are_kept(original: bytes) -> None:
    locator = PdfLocator(page=0, box=Box(x0=100, y0=790, x1=500, y1=800), baseline=798, font_size=8)

    words = _words(export_pdf(original, [(locator, "Dvořák – Zürich 100 €")]))

    assert " ".join(t for r, t in words if r.y0 > 789) == "Dvořák – Zürich 100 €"
