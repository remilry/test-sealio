"""Answers one form section with one model call: search per field → prompt → model → validator.

The only module that talks to `app.llm`. The model sees the section's fields, the passages found
for each of them (deduplicated) and the tender details, and must quote what it answers from.
"""

import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.llm.facade import LLM, LLMRequest, LLMUsage
from app.modules.filling.groups import CallGroup, FieldToAnswer
from app.modules.filling.llm_schema import LLMFieldAnswer, LLMSectionAnswer
from app.modules.filling.validator import (
    SourcePassage,
    ValidatedField,
    merge_runs,
    validate_field,
)
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
- If the field only applies to a case the passages show the bidder is not in (a question for \
foreign bidders when the bidder is Swiss, services performed abroad when none are), return no \
candidate.
- Otherwise give one answer: the complete value the field asks for, on one line, as it should be \
written in the form: the value only, without the document's labels or surrounding words ("14", \
not "14 with higher professional training"; "+41 44 555 01 20", not "Reception +41 44 555 01 20"). \
When the field asks for several facts (a name and a legal form), combine them in that one value, \
with one quote per fact; a field asking for an office, a company or a person with its address \
gets the name and the address. When the passages list several people, numbers or addresses, \
choose the one that fits the field: they are options, not a disagreement.
- A number must count exactly what the field asks for: a broader or different category ("other \
staff and apprentices" for auxiliary staff) is not an answer. Likewise, a list holds only \
items of the kind the field asks for (certificates are certifications, not insurance policies).
- When different documents give different values for the same fact (two addresses for the same \
office, two headcounts), give one candidate per value, each with its own quotes and its \
document's date, even when you think one of them is out of date: do not choose between documents \
yourself, the user decides. Give a second candidate only in that case.
- Each value must be made only of words found in its quotes, and each quote copied exactly from \
the passage it cites: a short excerpt taken from a single line of a single passage (quote two \
lines as two quotes). Within one document, prefer the current state over the history it \
records itself (an entry it marks as modified or deleted, a former address it names as such); \
when the only figure found comes from an older document (a past year's report), \
still give it, with that document's date.
- For a Yes/No field, answer "yes" or "no" only if a passage states it; quote that statement. A \
passage saying that the rule asked about does not apply to the bidder (no collective agreement \
applies) does not answer whether the bidder complies with it: return no candidate.
- For every candidate, return the date of the document it comes from and its end of validity \
when the document states them, with the quote stating each, even when the value itself comes \
from a table or another part of that document. The document's date is when it was issued or \
written (its "Issued:" line, the date in its letterhead, a report's year), never the date of an \
event it records (an incorporation, a register entry, a capital increase).
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


Search = Callable[[str, int], list[SourcePassage]]
# Called with a field's id and its verified evidence, as soon as the field is complete.
OnField = Callable[[int, ValidatedField], None]
# Called with a field's id and the value the model is writing for it (not verified yet).
OnWriting = Callable[[int, str], None]


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


def request_key(form_file_name: str, section: str, part: int | None = None) -> str:
    """Stable name of a call, for recorded answers: "annex-7-…--page-1", and
    "annex-4-…--table-7--part-2" for a part of a section cut in several calls."""
    key = f"{_slug(form_file_name.rsplit('.', 1)[0])}--{_slug(section)}"
    return key if part is None else f"{key}--part-{part}"


def answer_section(
    llm: LLM,
    *,
    company: str,
    form_title: str,
    form_file_name: str,
    group: CallGroup,
    search: Search,
    tender_details: str,
    today: date,
    on_field: OnField | None = None,
    on_writing: OnWriting | None = None,
    runs: int = 1,
) -> SectionResult:
    """The verified evidence of each field of the group, with what finding it cost.

    The call is made `runs` times at once (1 or 2) and the runs merged (`merge_runs`): the model
    does not answer the same way every time, so what differs between runs becomes a doubt.
    With `on_field`, each field is published as soon as every run has written its answer; the
    fields a run did not answer count as not found for that run, at the end.
    With `on_writing`, the value the first run is writing for a text field is reported as it
    grows (unverified: the field's published evidence replaces it).
    """
    fields = group.fields
    started = time.monotonic()
    passages = _passages(fields, search, tender_details)
    search_seconds = time.monotonic() - started

    request = _section_request(
        company=company,
        form_title=form_title,
        key=request_key(form_file_name, group.section, group.part),
        section=group.section,
        fields=fields,
        passages=passages,
        today=today,
    )
    merged = _MergedEvidence(fields, runs, on_field)
    requests = [request] + [
        replace(request, key=f"{request.key}--run-{run}") for run in range(2, runs + 1)
    ]

    def call(run: int) -> LLMUsage:
        evidence = _SectionEvidence(
            fields,
            passages,
            lambda f, e: merged.add(run, f, e),
            on_writing if run == 0 else None,
        )
        result = llm.generate_structured(requests[run], evidence.add_streamed)
        evidence.add_all(result.output.fields)
        evidence.add_not_found()
        return result.usage

    if runs == 1:
        usage = call(0)
    else:
        with ThreadPoolExecutor(max_workers=runs) as pool:
            usage = sum(pool.map(call, range(runs)), LLMUsage())

    return SectionResult(
        evidence=merged.by_field(),
        passages=len(passages),
        search_seconds=search_seconds,
        usage=usage,
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
        on_writing: OnWriting | None = None,
    ) -> None:
        self._fields = fields
        self._passages = passages
        self._on_field = on_field
        self._on_writing = on_writing
        self._writing: dict[int, str] = {}
        self._evidence: dict[int, ValidatedField] = {}

    def add_streamed(self, partial: dict[str, Any]) -> None:
        """The answers complete so far in the model's partial output (called while it writes)."""
        self.add_all(_complete_answers(partial))
        if self._on_writing is not None:
            self._report_writing(self._on_writing, partial)

    def _report_writing(self, on_writing: OnWriting, partial: dict[str, Any]) -> None:
        """The value of the answer still being written, when it grew (text fields only)."""
        items = partial.get("fields")
        if not isinstance(items, list) or not items or not isinstance(items[-1], dict):
            return
        item: dict[str, Any] = items[-1]
        name = item.get("field")
        # The key is complete once the next property has started.
        if not isinstance(name, str) or "user_only" not in item:
            return
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return
        first = candidates[0]
        text = first.get("value") if isinstance(first, dict) else None
        if not isinstance(text, str) or not text.strip():
            return
        field = _field_named(self._fields, name)
        if field is None or field.kind != FieldKind.TEXT or self._has(field):
            return
        if self._writing.get(field.id) == text:
            return
        self._writing[field.id] = text
        on_writing(field.id, text)

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


class _MergedEvidence:
    """The evidence of every run of a group's call: a field is merged and published once all the
    runs have validated it (runs write from their own threads)."""

    def __init__(self, fields: list[FieldToAnswer], runs: int, on_field: OnField | None) -> None:
        self._fields = fields
        self._runs = runs
        self._on_field = on_field
        self._by_run: dict[int, dict[int, ValidatedField]] = {}
        self._merged: dict[int, ValidatedField] = {}
        self._lock = threading.Lock()

    def add(self, run: int, field_id: int, evidence: ValidatedField) -> None:
        with self._lock:
            self._by_run.setdefault(field_id, {})[run] = evidence
            runs = self._by_run[field_id]
            if len(runs) < self._runs:
                return
            merged = runs[0]
            for other in range(1, self._runs):
                merged = merge_runs(merged, runs[other])
            self._merged[field_id] = merged
            if self._on_field is not None:
                self._on_field(field_id, merged)

    def by_field(self) -> dict[int, ValidatedField]:
        return {field.id: self._merged[field.id] for field in self._fields}


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
    return _field_named(fields, answer.field)


def _field_named(fields: list[FieldToAnswer], answered: str) -> FieldToAnswer | None:
    name = _normalized(answered)
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
    key: str,
    section: str,
    fields: list[FieldToAnswer],
    passages: list[SourcePassage],
    today: date,
) -> LLMRequest[LLMSectionAnswer]:
    """The model call for one group: its fields and the passages to answer them from."""
    return LLMRequest(
        key=key,
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
        for passage in search(field.query, SEARCH_K):
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
    context = f" · context: {field.context}" if field.context else ""
    return f"- key: {field.key} · label: {field.label}{context} · kind: {_kind(field.kind)}"


def _render(passage: SourcePassage) -> str:
    where = passage.document_name
    if passage.page is not None:
        where += f", page {passage.page + 1}"
    return f"[{passage.label}] {where}\n{passage.text}"


def _kind(kind: FieldKind) -> str:
    return "Yes/No" if kind == FieldKind.YES_NO else kind.value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
