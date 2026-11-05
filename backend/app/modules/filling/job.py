"""The AI fill of a form, run in the background, one section at a time.

Every step is recorded as a `fill_event` (committed at once) so the screen can follow it live and
replay it after a reload (docs/USER_FLOW.md §3.4, the five phases):
reading_form → detecting_fields → searching (a "field" event per answer) → cross_checking →
preparing_review → done (or error).
"""

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date
from itertools import groupby

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.llm.facade import LLM, LLMError, LLMUsage
from app.modules.filling import service
from app.modules.filling.answer_engine import Search, SectionResult, answer_section
from app.modules.filling.groups import CallGroup, FieldToAnswer, call_groups
from app.modules.filling.models import AiStatus, FillEventType, FormFill
from app.modules.filling.rules import AnswerType, Decision, decide
from app.modules.filling.validator import SourcePassage, ValidatedField
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = (
    "Something went wrong while filling this form. Discard its answers to auto-fill it again."
)
# The model failed (rate limit, timeout, no usable answer): its details go to the logs only.
MODEL_ERROR = "Answers could not be found right now. Discard the answers to auto-fill again."


class _Discarded(Exception):
    """The user discarded the fill while it was running: stop, silently."""


class _Stopped(Exception):
    """Another group of the fill failed or saw it discarded: this one stops publishing."""


def run_groups[T, R](
    items: Sequence[T], work: Callable[[T], R], *, max_workers: int, stop: threading.Event
) -> list[R]:
    """`work` on every item, up to `max_workers` at once; the results in the items' order.

    On the first exception, `stop` is set, the items not started yet are skipped, and that
    exception is raised once the running ones have ended (a model call cannot be interrupted:
    they check `stop` before publishing)."""
    if not items:
        return []

    def guarded(item: T) -> R:
        if stop.is_set():
            raise _Stopped
        try:
            return work(item)
        except BaseException:
            stop.set()
            raise

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(guarded, item) for item in items]
        wait(futures)
    errors = [f.exception() for f in futures if f.exception() is not None]
    first = next((e for e in errors if not isinstance(e, _Stopped)), None) or next(
        iter(errors), None
    )
    if first is not None:
        raise first
    return [f.result() for f in futures]


def _publish(
    session: Session,
    fill_id: int,
    tenant_id: int,
    form_id: int,
    field_id: int,
    decision: Decision,
    types: Counter[AnswerType],
) -> None:
    """Write a field's answer (unless the user set it meanwhile) and its "answered" event."""
    service.record_ai_answer(session, fill_id, field_id, decision)
    session.commit()
    answer = service.get_answer(session, fill_id, field_id)
    if answer is None:
        return
    if answer.resolved_by == "ai":
        types[decision.type] += 1
    counts = service.get_fill_state(session, tenant_id, form_id).counts
    service.add_event(
        session,
        fill_id,
        FillEventType.FIELD,
        {
            "field_id": field_id,
            "state": "answered",
            "answer": answer.model_dump(mode="json"),
            "counts": counts.model_dump(),
        },
    )


def run_fill(fill_id: int, llm: LLM, today: date | None = None) -> None:
    """Fill the form with the AI. Never raises: a failure ends the run with an "error" event.
    A fill discarded meanwhile ends the run silently (nothing is written into it, or into a new
    fill started since: the ids differ)."""
    with SessionLocal() as session:
        try:
            _run(session, fill_id, llm, today or date.today())
        except _Discarded, _Stopped:
            session.rollback()
            logger.info("AI fill %s was discarded, stopped", fill_id)
        except Exception as error:
            session.rollback()
            if not service.fill_exists(session, fill_id):
                # Gone while writing (a foreign key fails): same as discarded.
                logger.info("AI fill %s was discarded, stopped", fill_id)
                return
            if isinstance(error, LLMError):
                logger.warning("AI fill %s failed: %s", fill_id, error)
                message = MODEL_ERROR
            else:
                logger.exception("AI fill %s failed", fill_id)
                message = UNEXPECTED_ERROR
            service.finish_ai_fill(session, fill_id, AiStatus.FAILED)
            service.add_event(session, fill_id, FillEventType.ERROR, {"message": message})


def knowledge_search(session: Session, tenant_id: int) -> Search:
    """The tenant's company knowledge, searched for the answer engine."""

    def search(query: str, k: int) -> list[SourcePassage]:
        return [
            SourcePassage(
                label="",
                text=p.text,
                document_name=p.document_name,
                document_id=p.document_id,
                chunk_id=p.chunk_id,
                page=p.page,
            )
            for p in knowledge_service.search(session, tenant_id, query, k=k)
        ]

    return search


def _run(session: Session, fill_id: int, llm: LLM, today: date) -> None:
    started = time.monotonic()
    fill = session.get_one(FormFill, fill_id)
    tenant_id, form = fill.tenant_id, forms_service.get_form(session, fill.form_id)
    sections = [section for section, _ in groupby(form.fields, key=lambda f: f.section)]

    def check_not_discarded() -> None:
        if not service.fill_exists(session, fill_id):
            raise _Discarded

    def phase(name: str, **data: object) -> None:
        check_not_discarded()
        service.add_event(session, fill_id, FillEventType.PHASE, {"phase": name, **data})

    phase(
        "reading_form",
        file_format=form.file_format,
        pages=len(form.pages),
        sections=len(sections),
    )
    kept = service.user_resolved_field_ids(session, fill_id)
    contexts = forms_service.field_contexts(session, form.id)
    groups = call_groups(
        [
            FieldToAnswer(f.id, f.key, f.label, f.kind, context=contexts[f.id], section=f.section)
            for f in form.fields
            if f.kind != FieldKind.SIGNATURE
        ],
        skip=kept,
    )
    to_answer = [field for group in groups for field in group.fields]
    phase(
        "detecting_fields",
        fields=len(form.fields),
        yes_no=sum(1 for f in form.fields if f.kind == FieldKind.YES_NO),
        signatures=sum(1 for f in form.fields if f.kind == FieldKind.SIGNATURE),
        # Fields the user already set are kept as they are.
        to_answer=len(to_answer),
    )
    phase(
        "searching",
        documents=knowledge_service.count_indexed_documents(session, tenant_id),
    )

    company = tenants_service.get_tenant_name(session, tenant_id)
    details = tenders_service.tender_details(session, form.tender_id)

    for field in to_answer:
        service.add_event(
            session, fill_id, FillEventType.FIELD, {"field_id": field.id, "state": "searching"}
        )

    types: Counter[AnswerType] = Counter()
    # One field published at a time, all groups together: events are committed in the order of
    # their ids, which the live stream relies on (it reads the ids after the last one it sent).
    publishing = threading.Lock()
    stop = threading.Event()

    def answer_group(group: CallGroup) -> SectionResult:
        with SessionLocal() as group_session:
            by_id = {f.id: f for f in group.fields}

            def on_field(field_id: int, validated: ValidatedField) -> None:
                field = by_id[field_id]
                for reason in validated.rejected:
                    logger.info("Field %s (%s): %s", field.key, field.id, reason)
                decision = decide(field.kind, validated, today)
                if decision is None:
                    return
                with publishing:
                    if stop.is_set():
                        raise _Stopped
                    if not service.fill_exists(group_session, fill_id):
                        stop.set()
                        raise _Discarded
                    _publish(group_session, fill_id, tenant_id, form.id, field.id, decision, types)

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
        name = group.section if group.part is None else f"{group.section} (part {group.part})"
        logger.info("AI fill %s, section %r: %s", fill_id, name, result.describe())
        return result

    results = run_groups(
        groups, answer_group, max_workers=get_settings().fill_max_parallel_calls, stop=stop
    )
    usage = sum((r.usage for r in results), LLMUsage())
    search_seconds = sum(r.search_seconds for r in results)

    phase(
        "cross_checking",
        conflicts=types[AnswerType.CONFLICT],
        outdated=types[AnswerType.OUTDATED],
    )
    phase("preparing_review")
    counts = service.get_fill_state(session, tenant_id, form.id).counts
    logger.info(
        "AI fill %s of %r done in %.1fs: %s/%s filled · search %.1fs · model %s",
        fill_id,
        form.file_name,
        time.monotonic() - started,
        counts.filled,
        counts.fillable,
        search_seconds,
        usage.describe(),
    )
    service.finish_ai_fill(session, fill_id, AiStatus.DONE)
    service.add_event(
        session,
        fill_id,
        FillEventType.DONE,
        {
            "filled": counts.filled,
            "fillable": counts.fillable,
            "doubts": counts.doubts,
            "seconds": round(time.monotonic() - started, 1),
        },
    )
