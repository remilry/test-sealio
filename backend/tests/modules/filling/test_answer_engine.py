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


TEAM = SourcePassage(
    label="",
    text="Team (June 2026): 14 with higher professional training, 5 other staff",
    document_name="Company brochure 2026",
    document_id=4,
    chunk_id=41,
    page=0,
)


def _field_answer(key: str, value: str | None, quote: str = "") -> dict[str, object]:
    candidates = (
        []
        if value is None
        else [
            {
                "value": value,
                "citations": [{"passage": "P2", "quote": quote}],
                "source_date": None,
                "valid_until": None,
            }
        ]
    )
    return {
        "field": key,
        "user_only": False,
        "user_only_reason": None,
        "suggested_value": None,
        "candidates": candidates,
    }


FIELDS_2 = [
    FieldToAnswer(1, "trained", "With higher professional training", FieldKind.TEXT, section="T4"),
    FieldToAnswer(2, "auxiliary", "Auxiliary staff", FieldKind.TEXT, section="T4"),
]


def _two_runs(first: list[dict[str, object]], second: list[dict[str, object]] | None):
    key = request_key(FILE, "T4")
    answers = {key: {"fields": first}}
    if second is not None:
        answers[f"{key}--run-2"] = {"fields": second}
    llm = FakeLLM(answers)
    published: list[int] = []
    result = answer_section(
        llm,
        company="Alpenlogic AG",
        form_title="Annex",
        form_file_name=FILE,
        group=CallGroup("T4", None, FIELDS_2),
        search=lambda query, k: [TEAM],
        tender_details="Tender",
        today=date(2026, 11, 5),
        on_field=lambda field_id, evidence: published.append(field_id),
        runs=2,
    )
    return llm, result, published


def test_a_group_is_answered_by_two_runs_of_the_call() -> None:
    same = [_field_answer("trained", "14", "14 with higher professional training")]

    llm, result, _ = _two_runs(same, same)

    key = request_key(FILE, "T4")
    assert sorted(r.key for r in llm.requests) == [key, f"{key}--run-2"]
    assert result.usage.calls == 2
    assert not result.evidence[1].unsure


def test_a_value_only_one_run_found_is_unsure() -> None:
    first = [
        _field_answer("trained", "14", "14 with higher professional training"),
        _field_answer("auxiliary", "5", "5 other staff"),
    ]
    second = [_field_answer("trained", "14", "14 with higher professional training")]

    _, result, _ = _two_runs(first, second)

    assert [c.value for c in result.evidence[2].candidates] == ["5"]
    assert result.evidence[2].unsure
    assert not result.evidence[1].unsure


def test_each_field_is_published_once_both_runs_have_answered_it() -> None:
    answers = [
        _field_answer("trained", "14", "14 with higher professional training"),
        _field_answer("auxiliary", None),
    ]

    _, _, published = _two_runs(answers, answers)

    assert sorted(published) == [1, 2]


def test_a_second_run_without_its_own_recording_replays_the_first() -> None:
    same = [_field_answer("trained", "14", "14 with higher professional training")]

    _, result, _ = _two_runs(same, None)

    assert [c.value for c in result.evidence[1].candidates] == ["14"]
    assert not result.evidence[1].unsure
