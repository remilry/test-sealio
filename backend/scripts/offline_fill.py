"""The answer engine run on every form as the AI fill does (same search, prompt, validator, rules),
without writing anything to the database: for recording the model's answers and evaluating them.

The calls run in parallel like in the fill (`fill_max_parallel_calls`), to measure its real time.
"""

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionLocal
from app.llm.facade import LLM, LLMUsage
from app.modules.filling.answer_engine import SectionResult, answer_section, request_key
from app.modules.filling.groups import CallGroup, FieldToAnswer, call_groups
from app.modules.filling.job import knowledge_search, run_groups
from app.modules.filling.rules import NEEDS_REVIEW, AnswerType, decide
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind
from app.modules.forms.schemas import FormDetail
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service

DEMO_DOCUMENTS = REPO_ROOT / "knowledge-base" / "documents"

# Called with the request key and the field key each time a field is answered (progress).
OnAnswered = Callable[[str, str], None]


@dataclass(frozen=True)
class CallResult:
    """One model call (a group of fields) and what it found."""

    form_key: str
    key: str
    group: CallGroup
    result: SectionResult


@dataclass
class FormRun:
    """What a fill of a form gives: each field's answer type and value, by field key."""

    form_key: str
    answers: dict[str, tuple[AnswerType, str | None]]
    # Fields the user is asked to look at (doubts, values to check, user-only fields).
    needs_review: set[str]
    usage: LLMUsage
    seconds: float
    calls: list[CallResult] = field(default_factory=list)


def form_key(file_name: str) -> str:
    """ "annex-4" for "Annex_4_Conditions….docx": the key of its ground truth."""
    return "-".join(slug(file_name).split("-")[:2])


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def add_demo_documents() -> None:
    """The demo company's documents, added and indexed as a user would (already there: kept)."""
    settings = get_settings()
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        if knowledge_service.count_indexed_documents(session, tenant_id) > 0:
            return
        for source in sorted(DEMO_DOCUMENTS.glob("*.*")):
            knowledge_service.import_document(session, tenant_id, source, settings.data_dir)
        session.commit()


def fill_forms(
    llm: LLM, *, form: str | None = None, on_answered: OnAnswered | None = None
) -> list[FormRun]:
    """Every parsed form (or those whose slugged file name starts with `form`), answered with the
    tenant's indexed documents. Raises SystemExit when there is no document or no such form."""
    settings = get_settings()
    today = date.today()
    with SessionLocal() as session:
        tenant_id = tenants_service.get_current_tenant_id(session)
        if knowledge_service.count_indexed_documents(session, tenant_id) == 0:
            raise SystemExit("No indexed document: add them in the app or with the demo ones.")
        company = tenants_service.get_tenant_name(session, tenant_id)
        calls: list[tuple[FormDetail, str, CallGroup]] = []
        for tender in tenders_service.list_tenders(session):
            details = tenders_service.tender_details(session, tender.id)
            for summary in forms_service.list_forms(session, tender.id):
                if summary.field_counts is None:
                    continue
                if form and not slug(summary.file_name).startswith(form):
                    continue
                detail = forms_service.get_form(session, summary.id)
                contexts = forms_service.field_contexts(session, detail.id)
                fields = [
                    FieldToAnswer(
                        f.id, f.key, f.label, f.kind, context=contexts[f.id], section=f.section
                    )
                    for f in detail.fields
                    if f.kind != FieldKind.SIGNATURE
                ]
                calls.extend((detail, details, group) for group in call_groups(fields))
    if not calls:
        raise SystemExit(f"No form matches {form!r}.")

    started = time.monotonic()

    def answer(call: tuple[FormDetail, str, CallGroup]) -> CallResult:
        detail, details, group = call
        key = request_key(detail.file_name, group.section, group.part)
        keys = {f.id: f.key for f in group.fields}

        def on_field(field_id: int, _evidence: object) -> None:
            if on_answered is not None:
                on_answered(key, keys[field_id])

        with SessionLocal() as group_session:
            result = answer_section(
                llm,
                company=company,
                form_title=detail.title,
                form_file_name=detail.file_name,
                group=group,
                search=knowledge_search(group_session, tenant_id),
                tender_details=details,
                today=today,
                on_field=on_field,
                runs=settings.fill_runs_per_call,
            )
        return CallResult(form_key(detail.file_name), key, group, result)

    results = run_groups(
        calls, answer, max_workers=settings.fill_max_parallel_calls, stop=threading.Event()
    )
    seconds = time.monotonic() - started
    runs: dict[str, FormRun] = {}
    for call in results:
        run = runs.setdefault(call.form_key, FormRun(call.form_key, {}, set(), LLMUsage(), seconds))
        run.usage += call.result.usage
        run.calls.append(call)
        for group_field in call.group.fields:
            decision = decide(group_field.kind, call.result.evidence[group_field.id], today)
            if decision is None:
                continue
            run.answers[group_field.key] = (decision.type, decision.value)
            if decision.type in NEEDS_REVIEW:
                run.needs_review.add(group_field.key)
    return list(runs.values())
