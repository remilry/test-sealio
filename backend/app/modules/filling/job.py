"""The AI fill of a form, run in the background, one section at a time.

Every step is recorded as a `fill_event` (committed at once) so the screen can follow it live and
replay it after a reload (docs/USER_FLOW.md §3.4, the five phases):
reading_form → detecting_fields → searching (a "field" event per answer) → cross_checking →
preparing_review → done (or error).
"""

import logging
import time
from collections import Counter
from datetime import date
from itertools import groupby

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.llm.facade import LLM, LLMError, LLMUsage
from app.modules.filling import service
from app.modules.filling.answer_engine import FieldToAnswer, Search, answer_section
from app.modules.filling.models import AiStatus, FillEventType, FormFill
from app.modules.filling.rules import AnswerType, decide
from app.modules.filling.validator import SourcePassage, ValidatedField
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = "Something went wrong while filling this form."


class _Discarded(Exception):
    """The user discarded the fill while it was running: stop, silently."""


def run_fill(fill_id: int, llm: LLM, today: date | None = None) -> None:
    """Fill the form with the AI. Never raises: a failure ends the run with an "error" event.
    A fill discarded meanwhile ends the run silently (nothing is written into it, or into a new
    fill started since: the ids differ)."""
    with SessionLocal() as session:
        try:
            _run(session, fill_id, llm, today or date.today())
        except _Discarded:
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
                message = str(error)
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
    to_answer = [f for f in form.fields if f.kind != FieldKind.SIGNATURE and f.id not in kept]
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

    search = knowledge_search(session, tenant_id)

    types: Counter[AnswerType] = Counter()
    usage, search_seconds = LLMUsage(), 0.0
    for section, section_fields in groupby(to_answer, key=lambda f: f.section):
        fields = [FieldToAnswer(f.id, f.key, f.label, f.kind) for f in section_fields]
        for field in fields:
            service.add_event(
                session, fill_id, FillEventType.FIELD, {"field_id": field.id, "state": "searching"}
            )

        by_id = {f.id: f for f in fields}

        def on_field(
            field_id: int, validated: ValidatedField, by_id: dict[int, FieldToAnswer] = by_id
        ) -> None:
            check_not_discarded()
            field = by_id[field_id]
            for reason in validated.rejected:
                logger.info("Field %s (%s): %s", field.key, field.id, reason)
            decision = decide(field.kind, validated, today)
            if decision is None:
                return
            service.record_ai_answer(session, fill_id, field.id, decision)
            session.commit()
            answer = service.get_answer(session, fill_id, field.id)
            if answer is None:
                return
            if answer.resolved_by == "ai":
                types[decision.type] += 1
            counts = service.get_fill_state(session, tenant_id, form.id).counts
            service.add_event(
                session,
                fill_id,
                FillEventType.FIELD,
                {
                    "field_id": field.id,
                    "state": "answered",
                    "answer": answer.model_dump(mode="json"),
                    "counts": counts.model_dump(),
                },
            )

        result = answer_section(
            llm,
            company=company,
            form_title=form.title,
            form_file_name=form.file_name,
            section=section,
            fields=fields,
            search=search,
            tender_details=details,
            today=today,
            on_field=on_field,
        )
        usage, search_seconds = usage + result.usage, search_seconds + result.search_seconds
        logger.info("AI fill %s, section %r: %s", fill_id, section, result.describe())

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
