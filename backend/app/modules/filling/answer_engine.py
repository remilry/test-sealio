"""Answers one form section with one model call: search per field → prompt → model → validator.

The only module that talks to `app.llm`. The model sees the section's fields, the passages found
for each of them (deduplicated) and the tender details, and must quote what it answers from.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from app.llm.facade import LLM, LLMRequest, LLMUsage
from app.modules.filling.llm_schema import LLMSectionAnswer
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
can confirm (for place and date: the city of the registered office and today's date).
- Otherwise list every distinct value the passages give for it, the most recent or most official \
first. Each value must be made only of words found in its quotes, and each quote copied exactly \
from the passage it cites. Prefer the current state over history (superseded entries, former \
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
) -> SectionResult:
    """The verified evidence of each field of the section, with what finding it cost."""
    started = time.monotonic()
    passages = _passages(fields, search, tender_details)
    search_seconds = time.monotonic() - started
    request = LLMRequest(
        key=request_key(form_file_name, section),
        instructions=INSTRUCTIONS.format(company=company),
        prompt=PROMPT.format(
            today=today.isoformat(),
            form=form_title,
            section=section,
            fields="\n".join(
                f"- key: {f.key} · label: {f.label} · kind: {_kind(f.kind)}" for f in fields
            ),
            passages="\n\n".join(_render(p) for p in passages),
        ),
        schema=LLMSectionAnswer,
    )
    result = llm.generate_structured(request)
    answers = {answer.field: answer for answer in result.output.fields}
    return SectionResult(
        evidence={f.id: validate_field(f.kind, answers.get(f.key), passages) for f in fields},
        passages=len(passages),
        search_seconds=search_seconds,
        usage=result.usage,
    )


def _passages(
    fields: list[FieldToAnswer], search: Search, tender_details: str
) -> list[SourcePassage]:
    """Tender details first, then each field's passages in rank order, each once, labelled."""
    found = [SourcePassage(label="", text=tender_details, document_name=TENDER_DETAILS)]
    seen: set[int] = set()
    for field in fields:
        for passage in search(field.label, SEARCH_K):
            if passage.chunk_id is not None and passage.chunk_id in seen:
                continue
            if passage.chunk_id is not None:
                seen.add(passage.chunk_id)
            found.append(passage)
    return [replace(passage, label=f"P{i}") for i, passage in enumerate(found, start=1)]


def _render(passage: SourcePassage) -> str:
    where = passage.document_name
    if passage.page is not None:
        where += f", page {passage.page + 1}"
    return f"[{passage.label}] {where}\n{passage.text}"


def _kind(kind: FieldKind) -> str:
    return "Yes/No" if kind == FieldKind.YES_NO else kind.value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
