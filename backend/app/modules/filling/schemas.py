from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.filling.models import ResolvedBy


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_id: int
    value: str | None
    resolved_by: ResolvedBy
    resolved_at: datetime


class FillCounts(BaseModel):
    """Fields the user can fill (signatures excluded), and how many have a value."""

    fillable: int
    filled: int
    empty: int


class FillState(BaseModel):
    """The answers of a form so far. Fields without an answer are not listed."""

    counts: FillCounts
    answers: list[AnswerOut]


class AnswerUpdate(BaseModel):
    """A value entered by the user; null or blank leaves the field empty."""

    value: str | None = Field(max_length=2000)
