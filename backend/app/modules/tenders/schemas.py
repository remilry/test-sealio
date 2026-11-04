from datetime import date

from pydantic import BaseModel, ConfigDict

from app.modules.filling.models import FillStatus
from app.modules.forms.schemas import FormInfo


class TenderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    title: str
    submission_deadline: date


class FormSummary(FormInfo):
    """A form as listed on its tender page, with where the current tenant is in filling it."""

    status: FillStatus


class TenderDetail(TenderSummary):
    procedure: str
    authority: str
    summary: str
    forms: list[FormSummary]
