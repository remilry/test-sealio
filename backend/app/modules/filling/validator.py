"""Checks the model's answer against the passages it was given (pure: no database, no network).

- A quote must be found in its passage (case, accents, spaces, punctuation and line-break
  hyphens tolerated). Not in the labelled passage, it may be in another one sent: the passage is
  then the one that holds it. Nowhere → the citation is dropped.
- Values are written on one line. Two values of which one only adds details to the other are
  the same answer.
- Every meaningful word and number of the value must appear in its verified quotes, after
  normalisation (case, accents, 100'000 = 100,000 = 100000, dates written in any usual way).
- A Yes/No is accepted only with a verified quote as evidence.
- A date (source date, end of validity) must be stated in its own verified quote.
- A candidate left without a verified quote is rejected; no candidate left → not found.
"""

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date

from pydantic import BaseModel

from app.modules.filling.llm_schema import LLMCandidate, LLMCitation, LLMDate, LLMFieldAnswer
from app.modules.forms.parsing.schema import FieldKind

# Shortest quote accepted, in letters and digits: below that, anything matches anything.
MIN_QUOTE_CHARS = 3
# A quote in pieces (lines, "…"): each piece says something on its own, and a piece follows the
# previous one closely (letters skipped, spaces and punctuation not counted): a shortened sentence
# or the next line, not two statements stitched from far apart.
MIN_PIECE_CHARS = 4
MAX_ELLIPSIS_GAP = 60
# The next line of a quote may be further: a table's row label, its column header, its values.
MAX_LINE_GAP = 200

# Linking words a value may add between quoted facts ("Alpenlogic AG, company limited by shares").
CONNECTORS = frozenset({"a", "an", "and", "or", "the", "of", "in", "at", "on", "to", "for", "by"})

YES_NO = {"yes": "yes", "no": "no"}


@dataclass(frozen=True)
class SourcePassage:
    """A passage sent to the model, labelled "P1", "P2"… in the prompt."""

    label: str
    text: str
    document_name: str
    # Null for the tender details, which are not a company document.
    document_id: int | None = None
    chunk_id: int | None = None
    page: int | None = None


class Citation(BaseModel):
    """A verified quote and where it comes from."""

    quote: str
    document_name: str
    document_id: int | None
    chunk_id: int | None
    page: int | None


class DatedCitation(BaseModel):
    date: date
    citation: Citation


class Candidate(BaseModel):
    """A value read from the passages, with its verified evidence."""

    value: str
    citations: list[Citation]
    source_date: DatedCitation | None = None
    valid_until: DatedCitation | None = None


@dataclass
class ValidatedField:
    candidates: list[Candidate]
    user_only: bool = False
    user_only_reason: str | None = None
    suggested_value: str | None = None
    # Why parts of the model's answer were dropped (logged, never shown as an answer).
    rejected: list[str] = field(default_factory=list)
    # Of two runs of the same call, only one found a value: proposed, for the user to check.
    unsure: bool = False


# Where a quote breaks into pieces: a line break, or where it was shortened ("...", "…").
ELLIPSIS = re.compile(r"\.{3,}|…")
PIECE_BREAK = re.compile(r"(\.{3,}|…|\n)")


def validate_field(
    kind: FieldKind, answer: LLMFieldAnswer | None, passages: list[SourcePassage]
) -> ValidatedField:
    """Keep only what the passages prove. A missing answer is a "not found"."""
    if answer is None:
        return ValidatedField(candidates=[], rejected=["no answer for this field"])
    if answer.user_only:
        suggestion = _one_line(answer.suggested_value or "") or None
        return ValidatedField(
            candidates=[],
            user_only=True,
            user_only_reason=answer.user_only_reason,
            suggested_value=suggestion,
        )
    result = ValidatedField(candidates=[])
    for proposed in answer.candidates:
        candidate = _validate_candidate(kind, proposed, passages, result.rejected)
        if candidate is not None:
            _add_candidate(result.candidates, candidate)
    return result


def merge_runs(first: ValidatedField, second: ValidatedField) -> ValidatedField:
    """The verified evidence of two runs of the same call, merged: the model does not answer the
    same way every time, so what differs becomes a doubt instead of a silent error.

    Same values → one candidate with the evidence of both; different values → both candidates
    (a conflict); a value only one run found → kept, unsure; a field one run leaves to the user
    → left to the user."""
    rejected = first.rejected + second.rejected
    for run in (first, second):
        if run.user_only:
            return replace(run, rejected=rejected)
    merged = ValidatedField(candidates=[], rejected=rejected)
    for candidate in [*first.candidates, *second.candidates]:
        _add_candidate(merged.candidates, candidate.model_copy(deep=True))
    merged.unsure = bool(first.candidates) != bool(second.candidates)
    return merged


def _add_candidate(candidates: list[Candidate], candidate: Candidate) -> None:
    same = next((c for c in candidates if _same_answer(c.value, candidate.value)), None)
    if same is None:
        candidates.append(candidate)
        return
    # The same answer from several sources is one candidate with all its evidence; the earlier
    # wording is kept.
    same.citations += [c for c in candidate.citations if c not in same.citations]
    same.source_date = _latest(same.source_date, candidate.source_date)
    same.valid_until = same.valid_until or candidate.valid_until


def find_citation(citation: LLMCitation, passages: list[SourcePassage]) -> Citation | None:
    """The citation if its quote is in a passage sent (the labelled one first), else None.

    A quote is made of pieces: its lines, and the parts of a line shortened with an ellipsis
    ("Alpenlogic AG … has been assessed"). It is found when its pieces are, in that order and
    close to each other (MAX_ELLIPSIS_GAP letters skipped after an ellipsis, MAX_LINE_GAP at a
    line break), in one passage, or else over
    passages that follow each other in one document (a quote over two neighbouring passages).
    Never over two documents, and never from pieces too short to say anything on their own."""
    pieces = _pieces(citation.quote)
    if sum(len(piece.letters) for piece in pieces) < MIN_QUOTE_CHARS:
        return None
    if any(p.after_ellipsis and len(p.letters) < MIN_PIECE_CHARS for p in pieces):
        return None
    labelled = [p for p in passages if p.label == citation.passage.strip()]
    ordered = labelled + [p for p in passages if p.label != citation.passage.strip()]
    for passage in ordered:
        if _contains_in_order(_letters(passage.text), pieces):
            return _cited(citation, passage)
    for passage in ordered:
        if passage.chunk_id is None or pieces[0].letters not in _letters(passage.text):
            continue
        following = _following_passages(passage, passages)
        if len(following) > 1 and _contains_in_order(
            "".join(_letters(p.text) for p in following), pieces
        ):
            return _cited(citation, passage)
    return None


def _following_passages(first: SourcePassage, passages: list[SourcePassage]) -> list[SourcePassage]:
    """`first`, then the passages sent that follow it in its document (chunks are numbered in
    reading order as the document is cut), as long as none is missing."""
    by_chunk = {p.chunk_id: p for p in passages if p.document_id == first.document_id}
    chain = [first]
    while (next_id := (chain[-1].chunk_id or 0) + 1) in by_chunk:
        chain.append(by_chunk[next_id])
    return chain


def _cited(citation: LLMCitation, passage: SourcePassage) -> Citation:
    return Citation(
        quote=citation.quote.strip(),
        document_name=passage.document_name,
        document_id=passage.document_id,
        chunk_id=passage.chunk_id,
        page=passage.page,
    )


@dataclass(frozen=True)
class _Piece:
    letters: str
    # After an ellipsis (the model shortened the text) rather than at a line break.
    after_ellipsis: bool

    @property
    def max_gap(self) -> int:
        return MAX_ELLIPSIS_GAP if self.after_ellipsis else MAX_LINE_GAP


def _pieces(quote: str) -> list[_Piece]:
    pieces: list[_Piece] = []
    after_ellipsis = False
    for part in PIECE_BREAK.split(quote):
        if ELLIPSIS.fullmatch(part):
            after_ellipsis = True
            continue
        if part == "\n":
            continue
        letters = _letters(part)
        if letters:
            pieces.append(_Piece(letters, after_ellipsis and bool(pieces)))
            after_ellipsis = False
    return pieces


def _contains_in_order(text: str, pieces: list[_Piece]) -> bool:
    """The pieces in that order, each close enough to the previous one (its `max_gap`)."""
    first = pieces[0].letters
    start = text.find(first)
    while start >= 0:
        end = start + len(first)
        for piece in pieces[1:]:
            found = text.find(piece.letters, end, end + piece.max_gap + len(piece.letters))
            if found < 0:
                break
            end = found + len(piece.letters)
        else:
            return True
        start = text.find(first, start + 1)
    return False


def value_is_supported(value: str, quotes: list[str]) -> bool:
    """Every meaningful word and number of the value appears in the quotes (normalised)."""
    wanted = _tokens(value) - CONNECTORS
    if not wanted:
        return False
    available = set().union(*(_tokens(quote) for quote in quotes)) if quotes else set()
    return wanted <= available


def normalize_value(value: str) -> str:
    """Comparable form of a value: two values with the same form are the same answer."""
    return " ".join(sorted(_tokens(value) - CONNECTORS))


def _validate_candidate(
    kind: FieldKind,
    proposed: LLMCandidate,
    passages: list[SourcePassage],
    rejected: list[str],
) -> Candidate | None:
    value = _one_line(proposed.value)
    citations = []
    for citation in proposed.citations:
        found = find_citation(citation, passages)
        if found is None:
            rejected.append(f"quote not found in the passages: {citation.quote!r}")
        else:
            citations.append(found)
    if not citations:
        rejected.append(f"no verified quote for {value!r}")
        return None
    if kind == FieldKind.YES_NO:
        value = YES_NO.get(value.lower(), "")
        if not value:
            rejected.append(f"not a yes/no answer: {proposed.value!r}")
            return None
    elif not value_is_supported(value, [c.quote for c in citations]):
        rejected.append(f"value not in its quotes: {value!r}")
        return None
    source_date = _validate_date(proposed.source_date, passages, rejected)
    if source_date is not None and _date_token(source_date.date) in _tokens(value):
        # The date the value states (an incorporation, an entry) is not when the document was
        # written: dropped, so an old fact from a recent document is not taken for old news.
        source_date = None
    return Candidate(
        value=value,
        citations=citations,
        source_date=source_date,
        valid_until=_validate_date(proposed.valid_until, passages, rejected),
    )


def _validate_date(
    proposed: LLMDate | None, passages: list[SourcePassage], rejected: list[str]
) -> DatedCitation | None:
    if proposed is None:
        return None
    try:
        day = date.fromisoformat(proposed.date.strip())
    except ValueError:
        rejected.append(f"not an ISO date: {proposed.date!r}")
        return None
    citation = find_citation(proposed.citation, passages)
    if citation is None or not _states(citation.quote, day):
        rejected.append(f"date not stated in its quote: {proposed.date!r}")
        return None
    return DatedCitation(date=day, citation=citation)


def _states(quote: str, day: date) -> bool:
    """The quote gives that date, or that month when the date is its first day ("June 2026")."""
    if _date_token(day) in _tokens(quote):
        return True
    if day.day != 1:
        return False
    names = [name for name, number in MONTHS.items() if number == day.month]
    folded = _fold(quote)
    return any(re.search(rf"\b{name}\.?,?\s+{day.year}\b", folded) for name in names)


def _latest(a: DatedCitation | None, b: DatedCitation | None) -> DatedCitation | None:
    if a is None or b is None:
        return a or b
    return a if a.date >= b.date else b


def _same_answer(a: str, b: str) -> bool:
    """Two values say the same when one only adds details to the other ("Pfingstweidstrasse 31,
    8005 Zurich" and "…, Switzerland"): not a disagreement between sources."""
    words_a, words_b = _tokens(a) - CONNECTORS, _tokens(b) - CONNECTORS
    if not words_a or not words_b:
        return a.casefold() == b.casefold()
    return words_a <= words_b or words_b <= words_a


def _one_line(value: str) -> str:
    """As written in a form field: on one line, single spaces."""
    return " ".join(value.split())


# --- normalisation ---------------------------------------------------------------------------

MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    # 14.03.2016 · 14/03/2016 (day first, as in Switzerland)
    (re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"), ("d", "m", "y")),
    # 2016-03-14
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d")),
    # 14 March 2016 · 14. March 2016
    (re.compile(rf"\b(\d{{1,2}})\.?\s+({_MONTH})\.?,?\s+(\d{{4}})\b"), ("d", "M", "y")),
    # March 14, 2016
    (re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b"), ("M", "d", "y")),
]
# Digit grouping: 100'000 (straight or typographic apostrophe) and 100,000. Not spaces:
# phone numbers are grouped by spaces.
_GROUPING = re.compile("(?<=\\d)['\u2019,](?=\\d{3}\\b)")


def _fold(text: str) -> str:
    """Lower case, without accents, with typographic variants made plain."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.casefold().replace("­", "")


def _letters(text: str) -> str:
    """Letters and digits only: what a quote must match, whatever the spacing and punctuation."""
    return "".join(c for c in _fold(text) if c.isalnum())


def _date_token(day: date) -> str:
    return f"d{day:%Y%m%d}"


def _replace_dates(text: str) -> str:
    for pattern, order in _DATE_PATTERNS:
        text = pattern.sub(lambda m, order=order: _date_match(m, order), text)
    return text


def _date_match(match: re.Match[str], order: tuple[str, str, str]) -> str:
    parts = dict(zip(order, match.groups(), strict=True))
    month = MONTHS[parts["M"]] if "M" in parts else int(parts["m"])
    try:
        day = date(int(parts["y"]), month, int(parts["d"]))
    except ValueError:
        return match.group(0)
    return f" {_date_token(day)} "


def _tokens(text: str) -> set[str]:
    text = _GROUPING.sub("", _replace_dates(_fold(text)))
    return set(re.findall(r"[a-z0-9]+", text))
