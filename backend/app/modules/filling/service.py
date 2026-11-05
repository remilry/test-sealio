"""Public API of the filling module (other modules only import this file).

Every function acts for one tenant: a form is shared, its fill and answers belong to the tenant.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, RuleViolationError
from app.modules.filling.models import (
    AiStatus,
    Answer,
    FillEvent,
    FillEventType,
    FillStatus,
    FormFill,
    ResolvedBy,
)
from app.modules.filling.rules import AnswerType, Decision
from app.modules.filling.schemas import AiRun, AnswerOut, FillCounts, FillState
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind

DOUBTS = frozenset({AnswerType.CONFLICT, AnswerType.OUTDATED})

INTERRUPTED = (
    "The server stopped while filling this form. Discard its answers to auto-fill it again."
)


def fill_statuses(
    session: Session, tenant_id: int, form_ids: Sequence[int]
) -> dict[int, FillStatus]:
    """The tenant's status of each form (not started when it has no fill yet)."""
    rows = session.execute(
        select(FormFill.form_id, FormFill.status).where(
            FormFill.tenant_id == tenant_id, FormFill.form_id.in_(form_ids)
        )
    ).all()
    found = {form_id: status for form_id, status in rows}
    return {form_id: found.get(form_id, FillStatus.NOT_STARTED) for form_id in form_ids}


def running_forms(session: Session, tenant_id: int, form_ids: Sequence[int]) -> set[int]:
    """The forms among `form_ids` that the tenant's auto-fill is running on."""
    return set(
        session.scalars(
            select(FormFill.form_id).where(
                FormFill.tenant_id == tenant_id,
                FormFill.form_id.in_(form_ids),
                FormFill.ai_status == AiStatus.RUNNING,
            )
        )
    )


def get_fill_state(session: Session, tenant_id: int, form_id: int) -> FillState:
    fields = forms_service.list_fields(session, form_id)
    fill = _get_fill(session, tenant_id, form_id)
    answers = (
        []
        if fill is None
        else session.scalars(select(Answer).where(Answer.form_fill_id == fill.id)).all()
    )
    by_field = {answer.field_id: answer for answer in answers}
    fillable = [field for field in fields if field.kind != FieldKind.SIGNATURE]
    filled = sum(1 for field in fillable if field.id in by_field and by_field[field.id].value)
    doubts = sum(
        1
        for answer in answers
        if answer.type in DOUBTS and answer.needs_review and answer.resolved_by == ResolvedBy.AI
    )
    return FillState(
        counts=FillCounts(
            fillable=len(fillable), filled=filled, empty=len(fillable) - filled, doubts=doubts
        ),
        # In the form's order.
        answers=[AnswerOut.model_validate(by_field[f.id]) for f in fields if f.id in by_field],
        ai_run=_ai_run(fill),
    )


def answer_values(session: Session, tenant_id: int, form_id: int) -> dict[int, str]:
    """The tenant's non-empty answers by field id."""
    return {
        answer.field_id: answer.value
        for answer in get_fill_state(session, tenant_id, form_id).answers
        if answer.value
    }


def set_answer(
    session: Session, tenant_id: int, form_id: int, field_id: int, value: str | None
) -> FillState:
    """Record the value the user entered for a field (blank → empty field).

    The user's value is final: an AI fill running or started later never replaces it. What the
    AI found (type, candidates) is kept, to show the evidence next to the user's choice.
    """
    field = forms_service.get_field(session, form_id, field_id)
    if field.kind == FieldKind.SIGNATURE:
        raise RuleViolationError("Signatures and stamps are never filled: sign the form by hand.")
    fill = _start_fill(session, tenant_id, form_id)
    if fill.status == FillStatus.NOT_STARTED:
        fill.status = FillStatus.IN_REVIEW
    values = {
        "value": (value or "").strip() or None,
        "resolved_by": ResolvedBy.USER,
        "resolved_at": datetime.now(UTC),
        "needs_review": False,
    }
    # Upsert: two saves of the same field at once never create two answers.
    session.execute(
        insert(Answer)
        .values(form_fill_id=fill.id, field_id=field_id, **values)
        .on_conflict_do_update(index_elements=["form_fill_id", "field_id"], set_=values)
    )
    session.commit()
    return get_fill_state(session, tenant_id, form_id)


def start_ai_fill(session: Session, tenant_id: int, form_id: int) -> int:
    """Mark the tenant's fill of the form as being filled by the AI; returns the fill id.

    The previous run's events are cleared (the screen replays the new run). Raises when the form
    cannot be parsed yet, when the AI is already filling it or when the form was already started
    (any answer or a previous run): its answers must be discarded first.
    """
    form = forms_service.get_form(session, form_id)
    if form.field_counts is None:
        raise RuleViolationError(
            "This form cannot be filled automatically yet: its format is not read."
        )
    _start_fill(session, tenant_id, form_id)
    # Locked: two clicks on "Fill with AI" never start two runs.
    fill = session.scalars(
        select(FormFill)
        .where(FormFill.tenant_id == tenant_id, FormFill.form_id == form_id)
        .with_for_update()
    ).one()
    if fill.ai_status == AiStatus.RUNNING:
        raise ConflictError("This form is already being filled.")
    if fill.status != FillStatus.NOT_STARTED:
        raise ConflictError(
            "This form has already been filled. Discard its answers to auto-fill it again."
        )
    session.execute(delete(FillEvent).where(FillEvent.form_fill_id == fill.id))
    fill.status = FillStatus.IN_REVIEW
    fill.ai_status = AiStatus.RUNNING
    fill.ai_started_at = datetime.now(UTC)
    fill.ai_finished_at = None
    session.commit()
    return fill.id


def discard_fill(session: Session, tenant_id: int, form_id: int) -> None:
    """Delete the tenant's fill of the form: every answer (the user's included), the run and its
    events go with it (cascade), and the form is "not started" again. Also while it is running:
    the job notices and stops. Does nothing when nothing was started."""
    forms_service.get_form(session, form_id)
    session.execute(
        delete(FormFill).where(FormFill.tenant_id == tenant_id, FormFill.form_id == form_id)
    )
    session.commit()


def discard_all_fills(session: Session, tenant_id: int) -> None:
    """`discard_fill` for every form of the tenant: all its forms are "not started" again."""
    session.execute(delete(FormFill).where(FormFill.tenant_id == tenant_id))
    session.commit()


def fill_exists(session: Session, fill_id: int) -> bool:
    """False once the fill was discarded. A plain read: it holds no row lock."""
    return session.scalar(select(FormFill.id).where(FormFill.id == fill_id)) is not None


def get_ai_run(session: Session, tenant_id: int, form_id: int) -> AiRun | None:
    forms_service.get_form(session, form_id)
    return _ai_run(_get_fill(session, tenant_id, form_id))


def fill_id_of(session: Session, tenant_id: int, form_id: int) -> int | None:
    fill = _get_fill(session, tenant_id, form_id)
    return None if fill is None else fill.id


def user_resolved_field_ids(session: Session, fill_id: int) -> set[int]:
    """Fields whose value the user set: the AI leaves them alone."""
    return set(
        session.scalars(
            select(Answer.field_id).where(
                Answer.form_fill_id == fill_id, Answer.resolved_by == ResolvedBy.USER
            )
        )
    )


def record_ai_answer(session: Session, fill_id: int, field_id: int, decision: Decision) -> None:
    """Write the AI's answer to a field, unless the user has set it meanwhile."""
    values = {
        "value": decision.value,
        "resolved_by": ResolvedBy.AI,
        "resolved_at": datetime.now(UTC),
        "type": decision.type,
        "candidates": [c.model_dump(mode="json") for c in decision.candidates],
        "user_only_reason": decision.user_only_reason,
        "needs_review": decision.needs_review,
    }
    session.execute(
        insert(Answer)
        .values(form_fill_id=fill_id, field_id=field_id, **values)
        .on_conflict_do_update(
            index_elements=["form_fill_id", "field_id"],
            set_=values,
            # The user's value wins, even when saved while the AI was answering.
            where=Answer.resolved_by != ResolvedBy.USER,
        )
    )


def get_answer(session: Session, fill_id: int, field_id: int) -> AnswerOut | None:
    answer = session.scalar(
        select(Answer).where(Answer.form_fill_id == fill_id, Answer.field_id == field_id)
    )
    return None if answer is None else AnswerOut.model_validate(answer)


def add_event(
    session: Session, fill_id: int, event_type: FillEventType, data: dict[str, Any]
) -> None:
    """Record an event of the running fill and commit, so the screen sees it at once."""
    session.add(FillEvent(form_fill_id=fill_id, type=event_type, data=data))
    session.commit()


def finish_ai_fill(session: Session, fill_id: int, status: AiStatus) -> None:
    fill = session.get_one(FormFill, fill_id)
    fill.ai_status = status
    fill.ai_finished_at = datetime.now(UTC)


def events_after(
    session: Session, fill_id: int, after_id: int
) -> tuple[AiStatus | None, list[FillEvent]]:
    """The run's status, then its events after `after_id`, read in that order: when the status
    is no longer "running", the events returned are the last ones."""
    status = session.scalar(select(FormFill.ai_status).where(FormFill.id == fill_id))
    events = session.scalars(
        select(FillEvent)
        .where(FillEvent.form_fill_id == fill_id, FillEvent.id > after_id)
        .order_by(FillEvent.id)
    ).all()
    return status, list(events)


def fail_interrupted_fills(session: Session) -> None:
    """At startup: fills left "running" (the server stopped) end as failed, with a message."""
    fills = session.scalars(select(FormFill).where(FormFill.ai_status == AiStatus.RUNNING)).all()
    for fill in fills:
        session.add(
            FillEvent(form_fill_id=fill.id, type=FillEventType.ERROR, data={"message": INTERRUPTED})
        )
        fill.ai_status = AiStatus.FAILED
        fill.ai_finished_at = datetime.now(UTC)
    session.commit()


def _ai_run(fill: FormFill | None) -> AiRun | None:
    if fill is None or fill.ai_status is None or fill.ai_started_at is None:
        return None
    return AiRun(
        status=fill.ai_status, started_at=fill.ai_started_at, finished_at=fill.ai_finished_at
    )


def _get_fill(session: Session, tenant_id: int, form_id: int) -> FormFill | None:
    return session.scalar(
        select(FormFill).where(FormFill.tenant_id == tenant_id, FormFill.form_id == form_id)
    )


def _start_fill(session: Session, tenant_id: int, form_id: int) -> FormFill:
    """The tenant's fill of the form, created on first use (safe when two requests race)."""
    session.execute(
        insert(FormFill)
        .values(tenant_id=tenant_id, form_id=form_id)
        .on_conflict_do_nothing(index_elements=["tenant_id", "form_id"])
    )
    return session.scalars(
        select(FormFill).where(FormFill.tenant_id == tenant_id, FormFill.form_id == form_id)
    ).one()
