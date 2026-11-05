"""The ground-truth check of a fill (scripts/ground_truth.py): what the Annex 4 must give."""

from app.modules.filling.rules import AnswerType
from scripts.ground_truth import ANNEX_4, check

AUTO, MISSING, OUTDATED, CONFLICT, DECLARATION = (
    AnswerType.AUTO,
    AnswerType.MISSING,
    AnswerType.OUTDATED,
    AnswerType.CONFLICT,
    AnswerType.DECLARATION,
)


def test_a_value_written_differently_still_matches() -> None:
    assert (
        check(ANNEX_4, {"share_capital": (AUTO, "CHF 500'000 (fully paid in)")})["share_capital"]
        is None
    )


def test_a_wrong_type_is_reported() -> None:
    problem = check(
        ANNEX_4,
        {"ahv_compensation_office_exact_address": (AUTO, "Hardturmstrasse 120, 8005 Zurich")},
    )["ahv_compensation_office_exact_address"]

    assert problem == "type auto, expected conflict"


def test_a_value_missing_its_expected_part_is_reported() -> None:
    problem = check(ANNEX_4, {"competent_tax_office_exact_address": (AUTO, "Steuerweg 12")})[
        "competent_tax_office_exact_address"
    ]

    assert problem == "'Steuerweg 12' lacks 'Cantonal Tax Office'"


def test_a_declaration_answered_no_where_none_or_yes_is_expected_is_reported() -> None:
    key = "do_you_comply_with_the_collective_employment_agreement_that_"

    assert check(ANNEX_4, {key: (DECLARATION, "no")})[key] == "'no' lacks 'yes'"
    assert check(ANNEX_4, {key: (MISSING, None)})[key] is None


def test_a_field_with_no_answer_is_reported() -> None:
    assert check(ANNEX_4, {})["uid"] == "no answer"


def test_every_checked_key_is_an_annex_4_field() -> None:
    from app.core.config import get_settings
    from app.modules.forms.parsing.docx_parser import parse_docx

    path = get_settings().seed_forms_dir / (
        "Annex_4_Conditions of Participation and Company Self-Declaration.docx"
    )
    keys = {f.key for f in parse_docx(path.read_bytes()).fields}

    assert set(ANNEX_4) <= keys


def test_every_checked_key_is_an_annex_7_field() -> None:
    from app.core.config import get_settings
    from app.modules.forms.parsing.pdf_parser import parse_pdf
    from scripts.ground_truth import ANNEX_7

    path = get_settings().seed_forms_dir / "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"
    keys = {f.key for f in parse_pdf(path.read_bytes()).fields if f.kind != "signature"}

    assert set(ANNEX_7) == keys


def test_the_recorded_annex_7_answers_match_its_ground_truth() -> None:
    from scripts.ground_truth import ANNEX_7, GROUND_TRUTH

    # What the recorded fill gives (tests/modules/filling/test_recorded_answers.py).
    answers: dict[str, tuple[AnswerType, str | None]] = {
        "project_number_project_title_project_name": (
            AUTO,
            "ZH-2026-0412 · Cloud Platform Services – Canton of Zurich",
        ),
        "name_of_the_contracting_authority": (
            AUTO,
            "Canton of Zurich, Office for Information Technology",
        ),
        "name_and_legal_form": (
            AUTO,
            "Alpenlogic AG, Company limited by shares (Aktiengesellschaft, AG)",
        ),
        "business_address": (AUTO, "Pfingstweidstrasse 31, 8005 Zurich"),
        "contact_person": (AUTO, "Marc Keller"),
        "telephone": (AUTO, "+41 44 555 01 20"),
        "e_mail": (AUTO, "marc.keller@alpenlogic.example"),
        "place_and_date": (AnswerType.MANUAL, "Zurich, 04.11.2026"),
        "first_name_s_and_surname_s": (AUTO, "Marc Keller"),
    }

    assert all(problem is None for problem in check(ANNEX_7, answers).values())
    assert GROUND_TRUTH == {"annex-4": ANNEX_4, "annex-7": ANNEX_7}
