"""The validator keeps only what the passages prove (no model call)."""

from datetime import date

import pytest

from app.modules.filling.llm_schema import LLMCandidate, LLMCitation, LLMDate, LLMFieldAnswer
from app.modules.filling.validator import (
    SourcePassage,
    normalize_value,
    validate_field,
    value_is_supported,
)
from app.modules.forms.parsing.schema import FieldKind

REGISTER = SourcePassage(
    label="P1",
    text="Company name: Alpenlogic AG\nLegal form: Company limited by shares (AG)\n"
    "Address: Pfingst-\nweidstrasse 31, 8005 Zürich\nEntered on 14.03.2016. Share capital: "
    "CHF 500'000.",
    document_name="Commercial register extract",
    document_id=1,
    chunk_id=11,
    page=0,
)
INSURANCE = SourcePassage(
    label="P2",
    text="Liability insurance certificate issued on 1 November 2025. Valid until 31 October 2026. "
    "Personal injury: CHF 10,000,000 per claim.",
    document_name="Liability insurance certificate",
    document_id=3,
    chunk_id=31,
    page=0,
)
TENDER = SourcePassage(
    label="P3",
    text="Contracting authority: Canton of Zurich, Office for Information Technology",
    document_name="Tender details",
)
PASSAGES = [REGISTER, INSURANCE, TENDER]


def answer(*candidates: LLMCandidate, **fields: object) -> LLMFieldAnswer:
    values: dict[str, object] = {
        "field": "f",
        "user_only": False,
        "user_only_reason": None,
        "suggested_value": None,
        "candidates": list(candidates),
    }
    return LLMFieldAnswer.model_validate(values | fields)


def candidate(
    value: str,
    *quotes: tuple[str, str],
    source_date: LLMDate | None = None,
    valid_until: LLMDate | None = None,
) -> LLMCandidate:
    return LLMCandidate(
        value=value,
        citations=[LLMCitation(passage=p, quote=q) for p, q in quotes],
        source_date=source_date,
        valid_until=valid_until,
    )


def test_a_value_read_in_its_quote_is_kept_with_its_source() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(candidate("Alpenlogic AG", ("P1", "Company name: Alpenlogic AG"))),
        PASSAGES,
    )

    [kept] = result.candidates
    assert kept.value == "Alpenlogic AG"
    [citation] = kept.citations
    assert (citation.document_name, citation.document_id, citation.chunk_id, citation.page) == (
        "Commercial register extract",
        1,
        11,
        0,
    )


def test_a_quote_tolerates_case_spaces_accents_and_line_break_hyphens() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(
            candidate(
                "Pfingstweidstrasse 31, 8005 Zurich", ("P1", "PFINGSTWEIDSTRASSE 31,  8005 Zurich")
            )
        ),
        PASSAGES,
    )

    assert [c.value for c in result.candidates] == ["Pfingstweidstrasse 31, 8005 Zurich"]


def test_a_quote_not_in_the_passages_is_rejected_and_the_field_is_not_found() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(candidate("CHE-123.456.789", ("P1", "UID: CHE-123.456.789"))),
        PASSAGES,
    )

    assert result.candidates == []
    assert any("quote not found" in reason for reason in result.rejected)


def test_a_quote_in_another_passage_than_its_label_is_attributed_to_that_passage() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(candidate("Canton of Zurich", ("P1", "Contracting authority: Canton of Zurich"))),
        PASSAGES,
    )

    [kept] = result.candidates
    assert kept.citations[0].document_name == "Tender details"
    assert kept.citations[0].document_id is None


def test_a_value_with_words_absent_from_its_quote_is_rejected() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(candidate("Alpenlogic Holding AG", ("P1", "Company name: Alpenlogic AG"))),
        PASSAGES,
    )

    assert result.candidates == []
    assert any("value not in its quotes" in reason for reason in result.rejected)


def test_a_value_made_of_several_quoted_facts_is_kept() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(
            candidate(
                "Alpenlogic AG, company limited by shares (AG)",
                ("P1", "Alpenlogic AG"),
                ("P1", "Company limited by shares (AG)"),
            )
        ),
        PASSAGES,
    )

    assert [len(c.citations) for c in result.candidates] == [2]


def test_only_the_verified_quotes_of_a_candidate_support_its_value() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(
            candidate(
                "Alpenlogic AG, Bahnhofstrasse 1",
                ("P1", "Alpenlogic AG"),
                ("P1", "Bahnhofstrasse 1"),
            )
        ),
        PASSAGES,
    )

    assert result.candidates == []


@pytest.mark.parametrize(
    ("value", "quote"),
    [
        ("CHF 500,000", "CHF 500'000"),
        ("500000", "CHF 500'000"),
        ("2016-03-14", "Entered on 14.03.2016"),
        ("14 March 2016", "Entered on 14.03.2016"),
        ("March 14, 2016", "14.03.2016"),
        ("Zürich", "8005 Zurich"),
    ],
)
def test_numbers_dates_and_accents_are_compared_normalised(value: str, quote: str) -> None:
    assert value_is_supported(value, [quote])


def test_phone_numbers_grouped_by_spaces_are_not_merged() -> None:
    assert value_is_supported("+41 44 555 01 20", ["Phone +41 44 555 01 20"])
    assert not value_is_supported("+41 44 555 01 21", ["Phone +41 44 555 01 20"])


def test_a_value_of_linking_words_only_is_not_supported() -> None:
    assert not value_is_supported("and the", ["and the"])


def test_a_yes_no_needs_a_verified_quote_as_evidence() -> None:
    proven = validate_field(
        FieldKind.YES_NO,
        answer(candidate("Yes", ("P2", "Valid until 31 October 2026"))),
        PASSAGES,
    )
    unproven = validate_field(
        FieldKind.YES_NO, answer(candidate("yes", ("P2", "All taxes paid"))), PASSAGES
    )
    not_yes_no = validate_field(
        FieldKind.YES_NO, answer(candidate("maybe", ("P2", "Valid until"))), PASSAGES
    )

    assert [c.value for c in proven.candidates] == ["yes"]
    assert unproven.candidates == []
    assert not_yes_no.candidates == []


def test_dates_are_kept_only_when_stated_in_their_quote() -> None:
    result = validate_field(
        FieldKind.NUMBER,
        answer(
            candidate(
                "CHF 10,000,000",
                ("P2", "Personal injury: CHF 10,000,000 per claim"),
                source_date=LLMDate(
                    date="2025-11-01",
                    citation=LLMCitation(passage="P2", quote="issued on 1 November 2025"),
                ),
                valid_until=LLMDate(
                    date="2027-10-31",
                    citation=LLMCitation(passage="P2", quote="Valid until 31 October 2026"),
                ),
            )
        ),
        PASSAGES,
    )

    [kept] = result.candidates
    assert kept.source_date is not None
    assert kept.source_date.date == date(2025, 11, 1)
    # The model's date is not the one its quote states: dropped, the value is kept.
    assert kept.valid_until is None


def test_the_same_value_from_two_sources_is_one_candidate_with_both_quotes() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(
            candidate("Alpenlogic AG", ("P1", "Alpenlogic AG")),
            candidate("ALPENLOGIC AG", ("P1", "Company name: Alpenlogic AG")),
        ),
        PASSAGES,
    )

    [merged] = result.candidates
    assert len(merged.citations) == 2


def test_a_user_only_field_keeps_its_reason_and_suggestion_without_evidence() -> None:
    result = validate_field(
        FieldKind.TEXT,
        answer(
            user_only=True,
            user_only_reason="The place and date of signing are yours to set.",
            suggested_value="Zurich, 4 November 2026",
        ),
        PASSAGES,
    )

    assert result.user_only
    assert result.suggested_value == "Zurich, 4 November 2026"
    assert result.candidates == []


def test_a_field_the_model_did_not_answer_is_not_found() -> None:
    assert validate_field(FieldKind.TEXT, None, PASSAGES).candidates == []


def test_values_that_differ_only_in_form_normalise_the_same() -> None:
    assert normalize_value("Hardturmstrasse 120, 8005 Zürich") == normalize_value(
        "hardturmstrasse 120 8005 zurich"
    )
    assert normalize_value("Hardturmstrasse 120") != normalize_value("Röntgenstrasse 17")
