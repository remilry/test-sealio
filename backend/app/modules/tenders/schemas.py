from datetime import date

from pydantic import BaseModel, ConfigDict

from app.modules.forms.schemas import FormSummary


class TenderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    title: str
    submission_deadline: date


class TenderDetail(TenderSummary):
    procedure: str
    authority: str
    summary: str
    forms: list[FormSummary]
