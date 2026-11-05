"""Call groups: a form section is answered by one model call, cut when it has too many fields."""

from app.modules.filling.answer_engine import FieldToAnswer, request_key
from app.modules.filling.groups import call_groups
from app.modules.forms.parsing.schema import FieldKind


def fields(section: str, count: int, start: int = 1) -> list[FieldToAnswer]:
    return [
        FieldToAnswer(i, f"f{i}", f"F{i}", FieldKind.TEXT, section=section)
        for i in range(start, start + count)
    ]


def test_a_section_of_10_fields_is_one_call() -> None:
    [group] = call_groups(fields("Table 1", 10))

    assert (group.section, group.part, len(group.fields)) == ("Table 1", None, 10)


def test_a_section_of_11_fields_is_cut_in_balanced_parts() -> None:
    groups = call_groups(fields("Table 7", 11))

    assert [(g.part, len(g.fields)) for g in groups] == [(1, 6), (2, 5)]


def test_a_section_of_18_fields_is_cut_in_two_parts_of_9() -> None:
    groups = call_groups(fields("Table 7", 18))

    assert [(g.part, [f.id for f in g.fields]) for g in groups] == [
        (1, list(range(1, 10))),
        (2, list(range(10, 19))),
    ]


def test_sections_keep_their_order() -> None:
    groups = call_groups(fields("Table 2", 2) + fields("Table 1", 1, start=3))

    assert [g.section for g in groups] == ["Table 2", "Table 1"]


def test_fields_set_by_the_user_are_skipped_without_moving_others() -> None:
    all_fields = fields("Table 7", 18)

    groups = call_groups(all_fields, skip={1, 2})

    assert [(g.part, [f.id for f in g.fields]) for g in groups] == [
        (1, list(range(3, 10))),
        (2, list(range(10, 19))),
    ]


def test_a_group_left_empty_is_dropped() -> None:
    groups = call_groups(fields("Table 7", 18), skip=set(range(10, 19)))

    assert [(g.part, len(g.fields)) for g in groups] == [(1, 9)]


def test_a_section_left_empty_is_dropped() -> None:
    assert call_groups(fields("Table 1", 2), skip={1, 2}) == []


def test_request_key_of_a_part() -> None:
    assert request_key("Annex 4.docx", "Table 7", 2) == "annex-4--table-7--part-2"
    assert request_key("Annex 4.docx", "Table 7") == "annex-4--table-7"
