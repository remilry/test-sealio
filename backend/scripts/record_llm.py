"""Record the real model's answers for every form section, for FakeLLM to replay (tests, e2e, dev).

Runs the answer engine exactly as the AI fill does (same search, prompt and validator), against
the dev database, with the real embedding model and OpenAI. Nothing is written to the database:
only `llm_recordings/<key>.json`, one file per section, to review and commit.

    uv run python -m scripts.record_llm                 # documents already added in the app
    uv run python -m scripts.record_llm --add-demo-documents
    uv run python -m scripts.record_llm --form annex-4    # one form only

The calls run in parallel like in the fill (fill_max_parallel_calls), to measure its real time.

Needs OPENAI_API_KEY (backend/.env) and costs a few cents per run.
"""

import argparse
import time
from datetime import date

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.migrations import upgrade_to_head
from app.llm.facade import LLM, LLMUsage
from app.llm.fake_adapter import FakeLLM, RecordingLLM
from app.llm.openai_adapter import OpenAILLM
from app.llm.retrying import RetryingLLM
from app.modules.filling.rules import NEEDS_REVIEW, AnswerType, decide
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.seed import seed
from scripts.ground_truth import GROUND_TRUTH, check
from scripts.offline_fill import add_demo_documents, fill_forms


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the real model's answers for FakeLLM.")
    parser.add_argument(
        "--add-demo-documents",
        action="store_true",
        help="add and index the demo documents first (as a user would in the app)",
    )
    parser.add_argument(
        "--form",
        help="only the forms whose file name, slugged, starts with this (e.g. annex-4)",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="replay the saved recordings instead (free): checks the current validator and rules",
    )
    args = parser.parse_args()
    settings = get_settings()
    llm: LLM
    if args.replay:
        llm = FakeLLM.from_dir(settings.llm_recordings_dir)
    else:
        if settings.openai_api_key is None:
            raise SystemExit("OPENAI_API_KEY is not set (backend/.env).")
        # Retried inside the recorder: only the attempt that worked is written.
        llm = RecordingLLM(
            RetryingLLM(
                OpenAILLM(
                    api_key=settings.openai_api_key.get_secret_value(),
                    model=settings.llm_model,
                    reasoning_effort=settings.llm_reasoning_effort,
                    prices=settings.llm_prices(),
                ),
                attempts=settings.llm_attempts,
                base_seconds=settings.llm_retry_base_seconds,
            ),
            settings.llm_recordings_dir,
        )
    upgrade_to_head(settings.database_url)
    with SessionLocal() as session:
        seed(session, settings)
    if args.add_demo_documents:
        add_demo_documents()
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        documents = knowledge_service.count_indexed_documents(session, tenant_id)
    print(f"{documents} indexed documents, model {settings.llm_model}")

    started = time.monotonic()

    def on_answered(key: str, field_key: str) -> None:
        print(f"  [+{time.monotonic() - started:5.1f}s] {key[-24:]}: {field_key}")

    runs = fill_forms(llm, form=args.form, on_answered=on_answered)
    calls = [call for run in runs for call in run.calls]
    today = date.today()
    print(f"{len(calls)} calls, {settings.fill_max_parallel_calls} at a time")
    total, search_seconds = LLMUsage(), 0.0
    for call in calls:
        total += call.result.usage
        search_seconds += call.result.search_seconds
        print(f"\n{call.key}\n  {call.result.describe()}")
        for field in call.group.fields:
            evidence = call.result.evidence[field.id]
            decision = decide(field.kind, evidence, today)
            if decision is not None:
                print(f"  {field.key:45} {decision.type:12} {decision.value!r}")
            for reason in evidence.rejected:
                print(f"  {'':45} rejected: {reason}")
    wall = max((run.seconds for run in runs), default=0.0)
    print(f"\nTotal: {wall:.1f}s wall · search {search_seconds:.1f}s · model {total.describe()}")
    for run in runs:
        expected = GROUND_TRUTH.get(run.form_key)
        if expected is not None:
            _print_check(run.form_key, check(expected, run.answers), run.answers)


def _print_check(
    form_key: str,
    problems: dict[str, str | None],
    answers: dict[str, tuple[AnswerType, str | None]],
) -> None:
    """OK, flagged (not as expected, but shown to the user as to check) or silent (wrong with no
    flag: what the user could miss)."""
    wrong = {key: problem for key, problem in problems.items() if problem is not None}
    flagged = {key for key in wrong if key in answers and answers[key][0] in NEEDS_REVIEW}
    print(
        f"\nGround truth, {form_key}: {len(problems) - len(wrong)}/{len(problems)} OK · "
        f"{len(flagged)} flagged to check · {len(wrong) - len(flagged)} silent"
    )
    for key, problem in wrong.items():
        print(f"  {'FLAGGED' if key in flagged else 'SILENT '} {key}: {problem}")


if __name__ == "__main__":
    main()
