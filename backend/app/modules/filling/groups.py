"""Call groups: the fields answered by one model call.

One call per form section, a section of more than MAX_FIELDS_PER_CALL fields cut in balanced
parts, so that the calls (run in parallel) take about the same time. Groups are cut from all the
fields but signatures, before the fields the user set are left out: a group's key and content do
not depend on what the user typed, and recorded answers stay valid on a form started by hand.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.modules.forms.parsing.schema import FieldKind

MAX_FIELDS_PER_CALL = 10


@dataclass(frozen=True)
class FieldToAnswer:
    id: int
    key: str
    label: str
    kind: FieldKind
    # The heading that covers the field in the form, if any.
    context: str | None = None
    section: str = ""

    @property
    def query(self) -> str:
        """What the field's passages are searched with."""
        return f"{self.context} {self.label}" if self.context else self.label


@dataclass(frozen=True)
class CallGroup:
    section: str
    # 1, 2… when the section is cut, None when it is answered by one call.
    part: int | None
    fields: list[FieldToAnswer]


def call_groups(fields: Sequence[FieldToAnswer], *, skip: Collection[int] = ()) -> list[CallGroup]:
    """The groups of `fields` (all but signatures, in form order), without the fields in `skip`;
    a group left empty is not called."""
    sections: dict[str, list[FieldToAnswer]] = {}
    for field in fields:
        sections.setdefault(field.section, []).append(field)
    groups: list[CallGroup] = []
    for section, section_fields in sections.items():
        parts = _balanced(section_fields)
        for index, part in enumerate(parts, start=1):
            kept = [field for field in part if field.id not in skip]
            if kept:
                groups.append(CallGroup(section, index if len(parts) > 1 else None, kept))
    return groups


def _balanced(fields: list[FieldToAnswer]) -> list[list[FieldToAnswer]]:
    """`fields` in ceil(n / MAX_FIELDS_PER_CALL) consecutive parts, sizes differing by at most
    one, the first ones larger."""
    count = -(-len(fields) // MAX_FIELDS_PER_CALL)
    size, extra = divmod(len(fields), count)
    parts: list[list[FieldToAnswer]] = []
    start = 0
    for index in range(count):
        end = start + size + (1 if index < extra else 0)
        parts.append(fields[start:end])
        start = end
    return parts
