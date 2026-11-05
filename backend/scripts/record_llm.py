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
import re
import threading
import time
from datetime import date

from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionLocal
from app.core.migrations import upgrade_to_head
from app.llm.facade import LLM, LLMUsage
from app.llm.fake_adapter import FakeLLM, RecordingLLM
from app.llm.openai_adapter import OpenAILLM
from app.modules.filling.answer_engine import SectionResult, answer_section, request_key
from app.modules.filling.groups import CallGroup, FieldToAnswer, call_groups
from app.modules.filling.job import knowledge_search, run_groups
from app.modules.filling.rules import AnswerType, decide
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind
from app.modules.forms.schemas import FormDetail
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service
from app.seed import seed
from scripts.ground_truth import ANNEX_4, check

DEMO_DOCUMENTS = REPO_ROOT / "knowledge-base" / "documents"
# Expected answers by form (knowledge-base/GROUND_TRUTH.md), by the start of its recording key.
GROUND_TRUTH = {"annex-4": ANNEX_4}


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
        llm = RecordingLLM(
            OpenAILLM(
                api_key=settings.openai_api_key.get_secret_value(),
                model=settings.llm_model,
                reasoning_effort=settings.llm_reasoning_effort,
                prices=settings.llm_prices(),
            ),
            settings.llm_recordings_dir,
        )
    upgrade_to_head(settings.database_url)
    with SessionLocal() as session:
        seed(session, settings)
        tenant_id = tenants_service.get_current_tenant_id(session)
        if args.add_demo_documents:
            for source in sorted(DEMO_DOCUMENTS.glob("*.*")):
                knowledge_service.import_document(session, tenant_id, source, settings.data_dir)
            session.commit()
        documents = knowledge_service.count_indexed_documents(session, tenant_id)
        if documents == 0:
            raise SystemExit(
                "No indexed document: add them in the app or pass --add-demo-documents."
            )
        print(f"{documents} indexed documents, model {settings.llm_model}")
        company = tenants_service.get_tenant_name(session, tenant_id)
        today = date.today()
        calls: list[tuple[FormDetail, str, CallGroup]] = []
        for tender in tenders_service.list_tenders(session):
            details = tenders_service.tender_details(session, tender.id)
            for summary in forms_service.list_forms(session, tender.id):
                if summary.field_counts is None:
                    continue
                if args.form and not _slug(summary.file_name).startswith(args.form):
                    continue
                form = forms_service.get_form(session, summary.id)
                contexts = forms_service.field_contexts(session, form.id)
                fields = [
                    FieldToAnswer(
                        f.id, f.key, f.label, f.kind, context=contexts[f.id], section=f.section
                    )
                    for f in form.fields
                    if f.kind != FieldKind.SIGNATURE
                ]
                calls.extend((form, details, group) for group in call_groups(fields))
    if not calls:
        raise SystemExit(f"No form matches --form {args.form!r}.")
    print(f"{len(calls)} calls, {settings.fill_max_parallel_calls} at a time")

    started = time.monotonic()

    def record(call: tuple[FormDetail, str, CallGroup]) -> tuple[str, CallGroup, SectionResult]:
        form, details, group = call
        key = request_key(form.file_name, group.section, group.part)
        keys = {f.id: f.key for f in group.fields}

        def on_field(field_id: int, _evidence: object) -> None:
            print(f"  [+{time.monotonic() - started:5.1f}s] {key[-24:]}: {keys[field_id]}")

        with SessionLocal() as group_session:
            result = answer_section(
                llm,
                company=company,
                form_title=form.title,
                form_file_name=form.file_name,
                group=group,
                search=knowledge_search(group_session, tenant_id),
                tender_details=details,
                today=today,
                on_field=on_field,
            )
        return key, group, result

    results = run_groups(
        calls, record, max_workers=settings.fill_max_parallel_calls, stop=threading.Event()
    )
    wall = time.monotonic() - started
    total, search_seconds = LLMUsage(), 0.0
    answers: dict[str, dict[str, tuple[AnswerType, str | None]]] = {}
    for key, group, result in results:
        total += result.usage
        search_seconds += result.search_seconds
        print(f"\n{key}\n  {result.describe()}")
        for field in group.fields:
            evidence = result.evidence[field.id]
            decision = decide(field.kind, evidence, today)
            if decision is not None:
                print(f"  {field.key:45} {decision.type:12} {decision.value!r}")
                form_key = key.split("--")[0]
                answers.setdefault(form_key, {})[field.key] = (decision.type, decision.value)
            for reason in evidence.rejected:
                print(f"  {'':45} rejected: {reason}")
    print(f"\nTotal: {wall:.1f}s wall · search {search_seconds:.1f}s · model {total.describe()}")
    for form_key, form_answers in answers.items():
        expected = GROUND_TRUTH.get(form_key.split("-conditions")[0])
        if expected is not None:
            _print_check(form_key, check(expected, form_answers))


def _print_check(form_key: str, problems: dict[str, str | None]) -> None:
    wrong = {key: problem for key, problem in problems.items() if problem is not None}
    print(f"\nGround truth, {form_key}: {len(problems) - len(wrong)}/{len(problems)} OK")
    for key, problem in wrong.items():
        print(f"  KO {key}: {problem}")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


if __name__ == "__main__":
    main()
