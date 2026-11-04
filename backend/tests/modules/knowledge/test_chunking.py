from app.modules.knowledge.chunking import chunk
from app.modules.knowledge.extraction import Box, TextBlock


def _block(text: str, page: int | None = 0, y: float = 0, heading: bool = False) -> TextBlock:
    box = None if page is None else Box(x0=50, y0=y, x1=300, y1=y + 10)
    return TextBlock(text=text, page=page, box=box, heading=heading)


def test_short_blocks_of_a_page_make_one_passage_framed_by_their_union() -> None:
    [passage] = chunk("Tax attestation", [_block("Tax office", y=100), _block("Paid", y=120)])

    assert passage.text == "Tax office\nPaid"
    assert passage.context == "Tax attestation"
    assert passage.page == 0
    assert passage.box == Box(x0=50, y0=100, x1=300, y1=130)


def test_a_passage_never_spans_two_pages() -> None:
    passages = chunk("Doc", [_block("end of page one", page=0), _block("page two", page=1)])

    assert [(p.page, p.text) for p in passages] == [(0, "end of page one"), (1, "page two")]


def test_a_passage_stays_under_the_size_limit_without_cutting_a_block() -> None:
    blocks = [_block("x" * 30, y=i * 12) for i in range(5)]

    passages = chunk("Doc", blocks, max_chars=70)

    assert [p.text.count("x") for p in passages] == [60, 60, 30]


def test_a_heading_opens_a_new_passage_and_names_its_section() -> None:
    blocks = [
        _block("Intro", page=None),
        _block("3. Health and safety", page=None, heading=True),
        _block("An officer is appointed.", page=None),
        _block("4. Wages", page=None, heading=True),
        _block("Customary wages are paid.", page=None),
    ]

    passages = chunk("HR policy", blocks)

    assert [(p.context, p.text) for p in passages] == [
        ("HR policy", "Intro"),
        ("HR policy — 3. Health and safety", "3. Health and safety\nAn officer is appointed."),
        ("HR policy — 4. Wages", "4. Wages\nCustomary wages are paid."),
    ]
    assert all(p.page is None and p.box is None for p in passages)
