from pydantic import BaseModel, ConfigDict

from app.modules.forms.models import FileFormat, FormStatus
from app.modules.forms.parsing.schema import FieldKind, PageSize, PdfLocator


class FieldCounts(BaseModel):
    """What the parser found in a form, as shown on its card."""

    fields: int
    yes_no: int
    signatures: int


class FormSummary(BaseModel):
    """A form as listed on its tender page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_name: str
    file_format: FileFormat
    status: FormStatus
    # Null while the form's format cannot be parsed yet (it cannot be filled either).
    field_counts: FieldCounts | None = None


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    section: str
    label: str
    kind: FieldKind
    locator: PdfLocator


class FormDetail(FormSummary):
    tender_id: int
    pages: list[PageSize]
    # In the form's order (reading order).
    fields: list[FieldOut]
