"""Public API of the filling module (other modules only import this file)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import RuleViolationError
from app.modules.filling.models import Answer, ResolvedBy
from app.modules.filling.schemas import AnswerOut, FillCounts, FillState
from app.modules.forms import service as forms_service
from app.modules.forms.parsing.schema import FieldKind


def get_fill_state(session: Session, form_id: int) -> FillState:
    fields = forms_service.list_fields(session, form_id)
    answers = session.scalars(
        select(Answer).where(Answer.field_id.in_([field.id for field in fields]))
    ).all()
    by_field = {answer.field_id: answer for answer in answers}
    fillable = [field for field in fields if field.kind != FieldKind.SIGNATURE]
    filled = sum(1 for field in fillable if field.id in by_field and by_field[field.id].value)
    return FillState(
        counts=FillCounts(fillable=len(fillable), filled=filled, empty=len(fillable) - filled),
        # In the form's order.
        answers=[AnswerOut.model_validate(by_field[f.id]) for f in fields if f.id in by_field],
    )


def answer_values(session: Session, form_id: int) -> dict[int, str]:
    """Non-empty answers by field id."""
    return {
        answer.field_id: answer.value
        for answer in get_fill_state(session, form_id).answers
        if answer.value
    }


def set_answer(session: Session, form_id: int, field_id: int, value: str | None) -> FillState:
    """Record the value the user entered for a field (blank → empty field)."""
    field = forms_service.get_field(session, form_id, field_id)
    if field.kind == FieldKind.SIGNATURE:
        raise RuleViolationError("Signatures and stamps are never filled: sign the form by hand.")
    value = (value or "").strip() or None
    answer = session.scalar(select(Answer).where(Answer.field_id == field_id))
    if answer is None:
        answer = Answer(field_id=field_id)
        session.add(answer)
    answer.value = value
    answer.resolved_by = ResolvedBy.USER
    answer.resolved_at = datetime.now(UTC)
    forms_service.mark_in_review(session, form_id)
    session.commit()
    return get_fill_state(session, form_id)
