"""Record the real model's answers for every form section, for FakeLLM to replay (tests, e2e, dev).

Runs the answer engine exactly as the AI fill does (same search, prompt and validator), against
the dev database, with the real embedding model and OpenAI. Nothing is written to the database:
only `llm_recordings/<key>.json`, one file per section, to review and commit.

    uv run python -m scripts.record_llm                 # documents already added in the app
    uv run python -m scripts.record_llm --add-demo-documents

Needs OPENAI_API_KEY (backend/.env) and costs a few cents per run.
"""

import argparse
from datetime import date
from itertools import groupby

from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionLocal
from app.core.migrations import upgrade_to_head
from app.llm.facade import LLMUsage
from app.llm.fake_adapter import RecordingLLM
from app.llm.openai_adapter import OpenAILLM
from app.modules.filling.answer_engine import FieldToAnswer, answer_section, request_key
from app.modules.filling.job import knowledge_search
from app.modules.filling.rules import decide
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service
from app.seed import seed

DEMO_DOCUMENTS = REPO_ROOT / "knowledge-base" / "documents"


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the real model's answers for FakeLLM.")
    parser.add_argument(
        "--add-demo-documents",
        action="store_true",
        help="add and index the demo documents first (as a user would in the app)",
    )
    args = parser.parse_args()
    settings = get_settings()
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
        search = knowledge_search(session, tenant_id)
        today = date.today()
        total, search_seconds = LLMUsage(), 0.0
        for tender in tenders_service.list_tenders(session):
            details = tenders_service.tender_details(session, tender.id)
            for summary in forms_service.list_forms(session, tender.id):
                if summary.field_counts is None:
                    continue
                form = forms_service.get_form(session, summary.id)
                fillable = [f for f in form.fields if f.kind != FieldKind.SIGNATURE]
                for section, fields in groupby(fillable, key=lambda f: f.section):
                    to_answer = [FieldToAnswer(f.id, f.key, f.label, f.kind) for f in fields]
                    key = request_key(form.file_name, section)
                    print(f"\n{key}")
                    result = answer_section(
                        llm,
                        company=company,
                        form_title=form.title,
                        form_file_name=form.file_name,
                        section=section,
                        fields=to_answer,
                        search=search,
                        tender_details=details,
                        today=today,
                    )
                    evidence = result.evidence
                    total += result.usage
                    search_seconds += result.search_seconds
                    print(f"  {result.describe()}")
                    for field in to_answer:
                        decision = decide(field.kind, evidence[field.id], today)
                        if decision is not None:
                            print(f"  {field.key:45} {decision.type:12} {decision.value!r}")
                        for reason in evidence[field.id].rejected:
                            print(f"  {'':45} rejected: {reason}")
        print(f"\nTotal: search {search_seconds:.1f}s · model {total.describe()}")


if __name__ == "__main__":
    main()
