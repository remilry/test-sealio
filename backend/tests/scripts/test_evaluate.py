"""The evaluation of a fill against the ground truth: what is right, flagged, or silently wrong."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.llm.facade import LLMUsage
from app.llm.fake_adapter import FakeLLM
from app.main import app
from app.modules.filling.rules import AnswerType
from scripts.evaluate import FormRun, score, stability
from scripts.ground_truth import GROUND_TRUTH, Expected, expect
from scripts.offline_fill import fill_forms
from tests.modules.helpers import add_demo_documents

AUTO, MISSING, CONFLICT = AnswerType.AUTO, AnswerType.MISSING, AnswerType.CONFLICT

EXPECTED: dict[str, Expected] = {
    "uid": expect(AUTO, contains=("CHE-123.456.789",)),
    "ahv": expect(CONFLICT, contains=("Hardturmstrasse 120",)),
    "capital": expect(AUTO, contains=("500000",)),
    "vat": expect(MISSING),
}


def run(answers: dict[str, tuple[AnswerType, str | None]], review: set[str]) -> FormRun:
    return FormRun("annex-4", answers, review, LLMUsage(), 1.0)


def test_a_run_is_scored_right_flagged_or_silently_wrong() -> None:
    scored = score(
        EXPECTED,
        run(
            {
                "uid": (AUTO, "CHE-123.456.789"),
                # Wrong, but shown to the user as a doubt.
                "ahv": (AnswerType.UNSURE, "Röntgenstrasse 17"),
                # Wrong and presented as sure: what the user could miss.
                "capital": (AUTO, "CHF 100,000"),
                "vat": (MISSING, None),
            },
            review={"ahv"},
        ),
    )

    assert (scored.checked, scored.correct, scored.flagged) == (4, 2, 1)
    assert scored.silent == ["capital"]
    assert (scored.not_found_correct, scored.not_found_expected) == (1, 1)


def test_fields_whose_verdict_changes_between_runs_are_unstable() -> None:
    right = run({"uid": (AUTO, "CHE-123.456.789"), "vat": (MISSING, None)}, set())
    wrong = run({"uid": (AUTO, "CHE-999"), "vat": (MISSING, None)}, set())

    assert stability([right, wrong], EXPECTED) == ["uid"]
    assert stability([right, right], EXPECTED) == []


@pytest.fixture
def documents() -> Iterator[None]:
    with TestClient(app):
        add_demo_documents()
        yield


@pytest.mark.usefixtures("documents")
def test_the_recordings_of_both_annexes_have_no_silent_error() -> None:
    replay = FakeLLM.from_dir(get_settings().llm_recordings_dir)

    runs = fill_forms(replay)

    assert sorted(r.form_key for r in runs) == ["annex-4", "annex-7"]
    for form_run in runs:
        assert score(GROUND_TRUTH[form_run.form_key], form_run).silent == []
