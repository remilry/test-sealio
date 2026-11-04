"""The answer engine publishes each field as soon as the model has finished writing it."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.llm.fake_adapter import CHUNKS, FakeLLM
from app.modules.filling.answer_engine import (
    FieldToAnswer,
    LLMFieldAnswer,
    SectionResult,
    answer_section,
    complete_items,
    request_key,
)
from app.modules.filling.validator import SourcePassage, ValidatedField
from app.modules.forms.parsing.schema import FieldKind

FILE = "annex.pdf"
SECTION = "Company"
QUOTE = "Alpenlogic AG, Zurich"


def _field(id: int, key: str, label: str) -> FieldToAnswer:
    return FieldToAnswer(id=id, key=key, label=label, kind=FieldKind.TEXT)


FIELDS = [_field(1, "name", "Company name"), _field(2, "city", "City"), _field(3, "uid", "UID")]


def _answer(key: str, value: str) -> dict[str, Any]:
    return {
        "field": key,
        "user_only": False,
        "user_only_reason": None,
        "suggested_value": None,
        "candidates": [
            {
                "value": value,
                "citations": [{"passage": "P2", "quote": value}],
                "source_date": None,
                "valid_until": None,
            }
        ],
    }


def _search(query: str, k: int) -> list[SourcePassage]:
    return [SourcePassage(label="", text=QUOTE, document_name="Register", chunk_id=1)]


def _run(
    answers: list[dict[str, Any]], on_field: Any = None, fields: list[FieldToAnswer] = FIELDS
) -> tuple[SectionResult, list[dict[str, Any]]]:
    """Runs a section; also returns the partials the model streamed (to know when things happen)."""
    llm = FakeLLM({request_key(FILE, SECTION): {"fields": answers}})
    result = answer_section(
        llm,
        company="Alpenlogic AG",
        form_title="Annex",
        form_file_name=FILE,
        section=SECTION,
        fields=fields,
        search=_search,
        tender_details="Tender",
        today=date(2026, 11, 4),
        on_field=on_field,
    )
    return result, []


def test_complete_items_of_nothing_is_empty() -> None:
    assert complete_items({}, "fields") == []
    assert complete_items({"fields": []}, "fields") == []


def test_the_last_item_may_still_be_written() -> None:
    assert complete_items({"fields": [{"a": 1}]}, "fields") == []


def test_complete_items_are_all_but_the_last() -> None:
    assert complete_items({"fields": [{"a": 1}, {"a": 2}]}, "fields") == [{"a": 1}]


def test_a_partial_cut_inside_a_string_gives_the_items_before() -> None:
    partial = {"fields": [{"a": "one"}, {"a": "tw"}]}
    assert complete_items(partial, "fields") == [{"a": "one"}]


def test_fields_are_published_while_the_model_writes(monkeypatch: Any) -> None:
    seen = 0
    published: list[tuple[int, int]] = []

    original = FakeLLM.generate_structured

    def counting(self: FakeLLM, request: Any, on_partial: Any = None) -> Any:
        def count(partial: dict[str, Any]) -> None:
            nonlocal seen
            seen += 1
            on_partial(partial)

        return original(self, request, count)

    monkeypatch.setattr(FakeLLM, "generate_structured", counting)
    answers = [_answer("name", "Alpenlogic AG"), _answer("city", "Zurich"), _answer("uid", "x")]
    _run(answers, lambda field_id, _: published.append((field_id, seen)))
    assert [p[0] for p in published] == [1, 2, 3]
    assert published[0][1] < CHUNKS


def test_each_field_is_published_once() -> None:
    # 3 answers: the JSON length is not a multiple of 20, chunks cut keys and strings.
    published: list[int] = []
    _run(
        [_answer("name", "Alpenlogic AG"), _answer("city", "Zurich"), _answer("uid", "CHE-1")],
        lambda field_id, _: published.append(field_id),
    )
    assert sorted(published) == [1, 2, 3]


def test_a_field_answered_by_its_label_is_matched() -> None:
    published: dict[int, ValidatedField] = {}
    _run(
        [_answer("Company name", "Alpenlogic AG")],
        lambda field_id, value: published.__setitem__(field_id, value),
        fields=[_field(1, "name", "Company name")],
    )
    assert [c.value for c in published[1].candidates] == ["Alpenlogic AG"]


def test_a_skipped_field_is_published_not_found_at_the_end() -> None:
    published: list[tuple[int, ValidatedField]] = []
    _run(
        [_answer("name", "Alpenlogic AG"), _answer("uid", "CHE-1")],
        lambda field_id, value: published.append((field_id, value)),
    )
    assert [p[0] for p in published] == [1, 3, 2]
    assert published[-1][1].candidates == []


def test_published_evidence_equals_the_final_evidence() -> None:
    published: dict[int, ValidatedField] = {}
    result, _ = _run(
        [_answer("name", "Alpenlogic AG"), _answer("city", "Zurich")],
        lambda field_id, value: published.__setitem__(field_id, value),
    )
    assert published == result.evidence
    assert set(published) == {1, 2, 3}


def test_an_error_raised_while_publishing_a_field_is_not_swallowed() -> None:
    # Only a malformed model item is skipped; a ValidationError from the caller propagates.
    def on_field(field_id: int, _: ValidatedField) -> None:
        if field_id == 1:  # published while the model writes
            LLMFieldAnswer.model_validate({})

    answers = [_answer("name", "Alpenlogic AG"), _answer("city", "Zurich"), _answer("uid", "x")]
    with pytest.raises(ValidationError):
        _run(answers, on_field)
