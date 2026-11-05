"""Answers one form section with one model call: search per field → prompt → model → validator.

The only module that talks to `app.llm`. The model sees the section's fields, the passages found
for each of them (deduplicated) and the tender details, and must quote what it answers from.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.llm.facade import LLM, LLMRequest, LLMUsage
from app.modules.filling.llm_schema import LLMFieldAnswer, LLMSectionAnswer
from app.modules.filling.validator import SourcePassage, ValidatedField, validate_field
from app.modules.forms.parsing.schema import FieldKind

# Passages searched per field (the search recall test measures this k, see test_search_recall).
SEARCH_K = 8

TENDER_DETAILS = "Tender details"

INSTRUCTIONS = """\
You fill in a form sent by a buyer to the bidder company {company}. You answer one section of the \
form at a time, only from the passages given: the bidder's company documents and the tender \
details. Accuracy matters more than completeness: a wrong answer can exclude the bidder from the \
tender or make it declare something false.

For each field:
- If, by its nature, only the bidder's representative can provide it (place and date of signing, \
a personal choice), set user_only with a short reason for the user. You may suggest a value they \
can confirm (for place and date: the city of the registered office and today's date, written \
day.month.year).
- Otherwise give one answer: the complete value the field asks for, on one line, as it should be \
written in the form. When the field asks for several facts (a name and a legal form), combine \
them in that one value, with one quote per fact. When the passages list several people, numbers \
or addresses, choose the one that fits the field: they are options, not a disagreement.
- Give a second candidate only when the sources disagree about the same fact (two documents \
giving two different addresses for the same office, two different headcounts), the most recent or \
most official first.
- Each value must be made only of words found in its quotes, and each quote copied exactly from \
the passage it cites. Prefer the current state over history (superseded entries, former \
addresses).
- For a Yes/No field, answer "yes" or "no" only if a passage states it; quote that statement.
- When a document gives its date or its end of validity, return it with the quote stating it.
- When the passages do not contain the answer, return no candidate. Never guess, never infer \
from general knowledge, never reuse a value given for another field unless the passage supports \
it for this one.
"""

PROMPT = """\
Today is {today}.

Form: {form}
Section: {section}

Fields to fill:
{fields}

Passages:
{passages}
"""


@dataclass(frozen=True)
class FieldToAnswer:
    id: int
    key: str
    label: str
    kind: FieldKind


Search = Callable[[str, int], list[SourcePassage]]
# Called with a field's id and its verified evidence, as soon as the field is complete.
OnField = Callable[[int, ValidatedField], None]


@dataclass(frozen=True)
class SectionResult:
    # The verified evidence of each field, by field id.
    evidence: dict[int, ValidatedField]
    # Passages sent to the model (tender details included).
    passages: int
    search_seconds: float
    usage: LLMUsage

    def describe(self) -> str:
        return (
            f"search {self.search_seconds:.1f}s ({self.passages} passages) · "
            f"model {self.usage.describe()}"
        )


def request_key(form_file_name: str, section: str) -> str:
    """Stable name of a section's call, for recorded answers: "annex-7-…--page-1"."""
    return f"{_slug(form_file_name.rsplit('.', 1)[0])}--{_slug(section)}"


def answer_section(
    llm: LLM,
    *,
    company: str,
    form_title: str,
    form_file_name: str,
    section: str,
    fields: list[FieldToAnswer],
    search: Search,
    tender_details: str,
    today: date,
    on_field: OnField | None = None,
) -> SectionResult:
    """The verified evidence of each field of the section, with what finding it cost.

    With `on_field`, each field is published as soon as the model has written its answer; the
    fields the model did not answer are published as not found at the end.
    """
    started = time.monotonic()
    passages = _passages(fields, search, tender_details)
    search_seconds = time.monotonic() - started

    request = _section_request(
        company=company,
        form_title=form_title,
        form_file_name=form_file_name,
        section=section,
        fields=fields,
        passages=passages,
        today=today,
    )
    evidence = _SectionEvidence(fields, passages, on_field)
    if on_field is None:
        result = llm.generate_structured(request)
    else:
        result = llm.generate_structured(request, evidence.add_streamed)
    evidence.add_all(result.output.fields)
    evidence.add_not_found()

    return SectionResult(
        evidence=evidence.by_field(),
        passages=len(passages),
        search_seconds=search_seconds,
        usage=result.usage,
    )


def complete_items(partial: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """The items of `partial[key]` the model has finished writing: all but the last."""
    items = partial.get(key)
    if not isinstance(items, list):
        return []
    return [item for item in items[:-1] if isinstance(item, dict)]


class _SectionEvidence:
    """The verified evidence of a section's fields: each field is validated and published once,
    from the first answer the model gives for it."""

    def __init__(
        self,
        fields: list[FieldToAnswer],
        passages: list[SourcePassage],
        on_field: OnField | None,
    ) -> None:
        self._fields = fields
        self._passages = passages
        self._on_field = on_field
        self._evidence: dict[int, ValidatedField] = {}

    def add_streamed(self, partial: dict[str, Any]) -> None:
        """The answers complete so far in the model's partial output (called while it writes)."""
        self.add_all(_complete_answers(partial))

    def add_all(self, answers: list[LLMFieldAnswer]) -> None:
        for answer in answers:
            self.add(answer)

    def add(self, answer: LLMFieldAnswer) -> None:
        field = _field_answered(self._fields, answer)
        if field is None or self._has(field):
            return
        self._record(field, answer)

    def add_not_found(self) -> None:
        """The fields the model gave no answer for: validated without one (not found)."""
        for field in self._fields:
            if not self._has(field):
                self._record(field, None)

    def by_field(self) -> dict[int, ValidatedField]:
        return {field.id: self._evidence[field.id] for field in self._fields}

    def _has(self, field: FieldToAnswer) -> bool:
        return field.id in self._evidence

    def _record(self, field: FieldToAnswer, answer: LLMFieldAnswer | None) -> None:
        evidence = validate_field(field.kind, answer, self._passages)
        self._evidence[field.id] = evidence
        if self._on_field is not None:
            self._on_field(field.id, evidence)


def _complete_answers(partial: dict[str, Any]) -> list[LLMFieldAnswer]:
    """The field answers the model has finished writing. A malformed one is skipped (it is
    validated here, so an error raised while publishing an answer still propagates)."""
    answers: list[LLMFieldAnswer] = []
    for item in complete_items(partial, "fields"):
        try:
            answers.append(LLMFieldAnswer.model_validate(item))
        except ValidationError:
            continue
    return answers


def _field_answered(fields: list[FieldToAnswer], answer: LLMFieldAnswer) -> FieldToAnswer | None:
    """The field an answer is for: by key, as the model is asked, else by label (models
    sometimes echo the label instead). None for a field that is not in the section."""
    name = _normalized(answer.field)
    for field in fields:
        if _normalized(field.key) == name:
            return field
    for field in fields:
        if _normalized(field.label) == name:
            return field
    return None


def _section_request(
    *,
    company: str,
    form_title: str,
    form_file_name: str,
    section: str,
    fields: list[FieldToAnswer],
    passages: list[SourcePassage],
    today: date,
) -> LLMRequest[LLMSectionAnswer]:
    """The model call for one section: its fields and the passages to answer them from."""
    return LLMRequest(
        key=request_key(form_file_name, section),
        instructions=INSTRUCTIONS.format(company=company),
        prompt=PROMPT.format(
            today=today.isoformat(),
            form=form_title,
            section=section,
            fields="\n".join(_describe_field(field) for field in fields),
            passages="\n\n".join(_render(passage) for passage in passages),
        ),
        schema=LLMSectionAnswer,
    )


def _passages(
    fields: list[FieldToAnswer], search: Search, tender_details: str
) -> list[SourcePassage]:
    """Tender details first, then each field's passages in rank order, each once, labelled."""
    found = [SourcePassage(label="", text=tender_details, document_name=TENDER_DETAILS)]
    seen_chunks: set[int] = set()
    for field in fields:
        for passage in search(field.label, SEARCH_K):
            if passage.chunk_id is not None:
                if passage.chunk_id in seen_chunks:
                    continue
                seen_chunks.add(passage.chunk_id)
            found.append(passage)
    return [replace(passage, label=f"P{i}") for i, passage in enumerate(found, start=1)]


def _normalized(text: str) -> str:
    """Case and spacing ignored: "Telephone " and "telephone" are the same name."""
    return " ".join(text.casefold().split())


def _describe_field(field: FieldToAnswer) -> str:
    return f"- key: {field.key} · label: {field.label} · kind: {_kind(field.kind)}"


def _render(passage: SourcePassage) -> str:
    where = passage.document_name
    if passage.page is not None:
        where += f", page {passage.page + 1}"
    return f"[{passage.label}] {where}\n{passage.text}"


def _kind(kind: FieldKind) -> str:
    return "Yes/No" if kind == FieldKind.YES_NO else kind.value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
