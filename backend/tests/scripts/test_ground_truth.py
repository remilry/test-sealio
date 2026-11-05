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
