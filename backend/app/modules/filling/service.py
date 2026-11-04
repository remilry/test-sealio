"""Public API of the filling module (other modules only import this file).

Every function acts for one tenant: a form is shared, its fill and answers belong to the tenant.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import RuleViolationError
from app.modules.filling.models import Answer, FillStatus, FormFill, ResolvedBy
from app.modules.filling.schemas import AnswerOut, FillCounts, FillState
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind


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


def get_fill_state(session: Session, tenant_id: int, form_id: int) -> FillState:
    fields = forms_service.list_fields(session, form_id)
    fill_id = _fill_id(session, tenant_id, form_id)
    answers = (
        []
        if fill_id is None
        else session.scalars(select(Answer).where(Answer.form_fill_id == fill_id)).all()
    )
    by_field = {answer.field_id: answer for answer in answers}
    fillable = [field for field in fields if field.kind != FieldKind.SIGNATURE]
    filled = sum(1 for field in fillable if field.id in by_field and by_field[field.id].value)
    return FillState(
        counts=FillCounts(fillable=len(fillable), filled=filled, empty=len(fillable) - filled),
        # In the form's order.
        answers=[AnswerOut.model_validate(by_field[f.id]) for f in fields if f.id in by_field],
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
    """Record the value the user entered for a field (blank → empty field)."""
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
    }
    # Upsert: two saves of the same field at once never create two answers.
    session.execute(
        insert(Answer)
        .values(form_fill_id=fill.id, field_id=field_id, **values)
        .on_conflict_do_update(index_elements=["form_fill_id", "field_id"], set_=values)
    )
    session.commit()
    return get_fill_state(session, tenant_id, form_id)


def _fill_id(session: Session, tenant_id: int, form_id: int) -> int | None:
    return session.scalar(
        select(FormFill.id).where(FormFill.tenant_id == tenant_id, FormFill.form_id == form_id)
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
