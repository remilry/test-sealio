"""Generic rules turning verified evidence into an answer (pure: no database, no network).

No rule knows a form or a field: they only look at the field's kind and at the evidence
(docs/USER_FLOW.md §4). In this order:
1. Signature or stamp → never filled.
2. Only the user can fill it → manual, with the suggested value pre-written.
3. Two or more different values → conflict, the most recent one selected.
4. Its source is no longer valid → outdated.
5. Yes/No with evidence → declaration, ticked; without → missing.
6. One value → automatic; none → missing.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.modules.filling.validator import Candidate, ValidatedField
from app.modules.forms.parsing.schema import FieldKind


class AnswerType(StrEnum):
    AUTO = "auto"
    MISSING = "missing"
    MANUAL = "manual"
    OUTDATED = "outdated"
    CONFLICT = "conflict"
    DECLARATION = "declaration"


# Types the user has to look at; the others are already in the form.
NEEDS_REVIEW = frozenset(
    {AnswerType.MISSING, AnswerType.MANUAL, AnswerType.OUTDATED, AnswerType.CONFLICT}
)


@dataclass(frozen=True)
class Decision:
    type: AnswerType
    # What goes into the form; null leaves the field empty.
    value: str | None
    # The selected candidate first.
    candidates: list[Candidate]
    user_only_reason: str | None = None

    @property
    def needs_review(self) -> bool:
        return self.type in NEEDS_REVIEW


def decide(kind: FieldKind, evidence: ValidatedField, today: date) -> Decision | None:
    """The answer to write for a field, or None when the AI must leave it alone (signature)."""
    if kind == FieldKind.SIGNATURE:
        return None
    if evidence.user_only:
        return Decision(
            AnswerType.MANUAL,
            evidence.suggested_value,
            [],
            user_only_reason=evidence.user_only_reason,
        )
    candidates = evidence.candidates
    if not candidates:
        return Decision(AnswerType.MISSING, None, [])
    if len(candidates) > 1:
        selected = _most_recent(candidates)
        ordered = [selected, *(c for c in candidates if c is not selected)]
        return Decision(AnswerType.CONFLICT, selected.value, ordered)
    [candidate] = candidates
    if candidate.valid_until is not None and candidate.valid_until.date < today:
        return Decision(AnswerType.OUTDATED, candidate.value, candidates)
    if kind == FieldKind.YES_NO:
        return Decision(AnswerType.DECLARATION, candidate.value, candidates)
    return Decision(AnswerType.AUTO, candidate.value, candidates)


def _most_recent(candidates: list[Candidate]) -> Candidate:
    """The candidate with the latest source date; the model's first choice when none is dated."""
    dated = [c for c in candidates if c.source_date is not None]
    if not dated:
        return candidates[0]
    return max(dated, key=lambda c: c.source_date.date if c.source_date else date.min)
