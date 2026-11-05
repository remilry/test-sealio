"""One case per generic rule (docs/USER_FLOW.md §4), no model call."""

from datetime import date

from app.modules.filling.rules import AnswerType, decide
from app.modules.filling.validator import Candidate, Citation, DatedCitation, ValidatedField
from app.modules.forms.parsing.schema import FieldKind

TODAY = date(2026, 11, 4)


def citation(quote: str = "quote") -> Citation:
    return Citation(quote=quote, document_name="Doc", document_id=1, chunk_id=1, page=0)


def dated(day: date) -> DatedCitation:
    return DatedCitation(date=day, citation=citation(str(day)))


def found(
    value: str, *, source_date: date | None = None, valid_until: date | None = None
) -> Candidate:
    return Candidate(
        value=value,
        citations=[citation()],
        source_date=dated(source_date) if source_date else None,
        valid_until=dated(valid_until) if valid_until else None,
    )


def test_a_signature_is_never_filled_even_with_evidence() -> None:
    assert decide(FieldKind.SIGNATURE, ValidatedField([found("Marc Keller")]), TODAY) is None


def test_one_verified_value_is_filled_automatically() -> None:
    decision = decide(FieldKind.TEXT, ValidatedField([found("Alpenlogic AG")]), TODAY)

    assert decision is not None
    assert (decision.type, decision.value, decision.needs_review) == (
        AnswerType.AUTO,
        "Alpenlogic AG",
        False,
    )


def test_no_verified_value_leaves_the_field_empty_for_the_user() -> None:
    decision = decide(FieldKind.TEXT, ValidatedField([]), TODAY)

    assert decision is not None
    assert (decision.type, decision.value, decision.needs_review) == (
        AnswerType.MISSING,
        None,
        True,
    )


def test_a_user_only_field_is_manual_with_its_suggestion_pre_written() -> None:
    evidence = ValidatedField(
        [found("ignored")],
        user_only=True,
        user_only_reason="Yours to set.",
        suggested_value="Zurich, 4 November 2026",
    )

    decision = decide(FieldKind.TEXT, evidence, TODAY)

    assert decision is not None
    assert decision.type == AnswerType.MANUAL
    assert decision.value == "Zurich, 4 November 2026"
    assert decision.user_only_reason == "Yours to set."
    assert decision.needs_review


def test_different_values_are_a_conflict_with_the_most_recent_selected() -> None:
    old = found("Röntgenstrasse 17", source_date=date(2024, 12, 31))
    new = found("Hardturmstrasse 120", source_date=date(2026, 1, 15))

    decision = decide(FieldKind.TEXT, ValidatedField([old, new]), TODAY)

    assert decision is not None
    assert decision.type == AnswerType.CONFLICT
    assert decision.value == "Hardturmstrasse 120"
    assert [c.value for c in decision.candidates] == ["Hardturmstrasse 120", "Röntgenstrasse 17"]
    assert decision.needs_review


def test_a_conflict_without_dates_keeps_the_models_first_choice() -> None:
    decision = decide(FieldKind.TEXT, ValidatedField([found("28"), found("31")]), TODAY)

    assert decision is not None
    assert (decision.type, decision.value) == (AnswerType.CONFLICT, "28")


def test_a_value_from_an_expired_source_is_outdated_but_proposed() -> None:
    decision = decide(
        FieldKind.NUMBER,
        ValidatedField([found("CHF 10,000,000", valid_until=date(2026, 10, 31))]),
        TODAY,
    )

    assert decision is not None
    assert (decision.type, decision.value, decision.needs_review) == (
        AnswerType.OUTDATED,
        "CHF 10,000,000",
        True,
    )


def test_a_source_valid_until_today_is_not_outdated() -> None:
    decision = decide(
        FieldKind.TEXT, ValidatedField([found("ISO 27001", valid_until=TODAY)]), TODAY
    )

    assert decision is not None
    assert decision.type == AnswerType.AUTO


def test_a_yes_no_with_evidence_is_a_ticked_declaration() -> None:
    decision = decide(FieldKind.YES_NO, ValidatedField([found("no")]), TODAY)

    assert decision is not None
    assert (decision.type, decision.value, decision.needs_review) == (
        AnswerType.DECLARATION,
        "no",
        False,
    )


def test_a_yes_no_without_evidence_is_left_to_the_user() -> None:
    decision = decide(FieldKind.YES_NO, ValidatedField([]), TODAY)

    assert decision is not None
    assert (decision.type, decision.value) == (AnswerType.MISSING, None)


def test_a_value_from_a_source_over_a_year_old_is_outdated_but_proposed() -> None:
    # A figure from the 2024 annual report: kept, flagged for the user to check.
    decision = decide(
        FieldKind.TEXT,
        ValidatedField([found("3", source_date=date(2024, 12, 31))]),
        TODAY,
    )

    assert decision is not None
    assert (decision.type, decision.value, decision.needs_review) == (
        AnswerType.OUTDATED,
        "3",
        True,
    )


def test_a_source_under_a_year_old_is_not_outdated() -> None:
    decision = decide(
        FieldKind.TEXT, ValidatedField([found("28", source_date=date(2025, 11, 5))]), TODAY
    )

    assert decision is not None
    assert decision.type == AnswerType.AUTO


def test_an_old_source_still_valid_is_not_outdated() -> None:
    # An ISO certificate issued years ago, valid until 2028.
    decision = decide(
        FieldKind.TEXT,
        ValidatedField(
            [found("ISO 9001", source_date=date(2022, 3, 12), valid_until=date(2028, 3, 12))]
        ),
        TODAY,
    )

    assert decision is not None
    assert decision.type == AnswerType.AUTO
