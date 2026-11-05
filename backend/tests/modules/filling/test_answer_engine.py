"""The answer engine's search queries and prompt, with and without a field's heading context."""

from datetime import date

from app.llm.fake_adapter import FakeLLM
from app.modules.filling.answer_engine import FieldToAnswer, answer_section, request_key
from app.modules.filling.groups import CallGroup
from app.modules.filling.validator import SourcePassage
from app.modules.forms.parsing.schema import FieldKind

FILE = "annex.docx"


def _answer(group: CallGroup) -> tuple[list[str], str]:
    queries: list[str] = []

    def search(query: str, k: int) -> list[SourcePassage]:
        queries.append(query)
        return []

    llm = FakeLLM({request_key(FILE, group.section, group.part): {"fields": []}})
    answer_section(
        llm,
        company="Alpenlogic AG",
        form_title="Annex",
        form_file_name=FILE,
        group=group,
        search=search,
        tender_details="Tender",
        today=date(2026, 11, 5),
    )
    [request] = llm.requests
    return queries, request.prompt


def test_a_field_with_a_heading_is_searched_and_described_with_it() -> None:
    field = FieldToAnswer(
        1,
        "personal_injury",
        "Personal injury",
        FieldKind.TEXT,
        context="Available amounts per claim",
        section="Table 5",
    )

    queries, prompt = _answer(CallGroup("Table 5", None, [field]))

    assert queries == ["Available amounts per claim Personal injury"]
    assert (
        "- key: personal_injury · label: Personal injury · context: Available amounts per claim "
        "· kind: text"
    ) in prompt


def test_a_field_without_a_heading_is_searched_by_its_label() -> None:
    field = FieldToAnswer(1, "uid", "UID", FieldKind.TEXT, section="Table 2")

    queries, prompt = _answer(CallGroup("Table 2", None, [field]))

    assert queries == ["UID"]
    assert "- key: uid · label: UID · kind: text" in prompt


def test_a_part_is_called_with_its_own_key_and_its_section_name() -> None:
    field = FieldToAnswer(1, "remarks", "Remarks", FieldKind.TEXT, section="Table 7")

    _, prompt = _answer(CallGroup("Table 7", 2, [field]))

    assert "Section: Table 7\n" in prompt
