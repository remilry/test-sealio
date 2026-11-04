from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.filling.models import AiStatus, ResolvedBy
from app.modules.filling.rules import AnswerType
from app.modules.filling.validator import Candidate


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_id: int
    value: str | None
    resolved_by: ResolvedBy
    resolved_at: datetime
    # What the AI found; null when the AI never answered this field.
    type: AnswerType | None
    # Verified evidence, the selected candidate first (two or more: a conflict).
    candidates: list[Candidate]
    # Why only the user can fill it (type "manual").
    user_only_reason: str | None
    # The user still has to look at it.
    needs_review: bool


class FillCounts(BaseModel):
    """Fields the user can fill (signatures excluded), how many have a value, how many doubts."""

    fillable: int
    filled: int
    empty: int
    # Conflicts and outdated sources the user has not reviewed yet.
    doubts: int


class AiRun(BaseModel):
    """The last AI fill of the form."""

    model_config = ConfigDict(from_attributes=True)

    status: AiStatus
    started_at: datetime
    finished_at: datetime | None


class FillState(BaseModel):
    """The answers of a form so far. Fields without an answer are not listed."""

    counts: FillCounts
    answers: list[AnswerOut]
    # Null when the AI never ran on this form.
    ai_run: AiRun | None


class AnswerUpdate(BaseModel):
    """A value entered by the user; null or blank leaves the field empty."""

    value: str | None = Field(max_length=2000)
