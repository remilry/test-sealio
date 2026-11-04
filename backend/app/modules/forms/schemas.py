from pydantic import BaseModel, ConfigDict

from app.modules.forms.models import FileFormat
from app.modules.forms.parsing.schema import FieldKind, PageSize, PdfLocator


class FieldCounts(BaseModel):
    """What the parser found in a form, as shown on its card."""

    fields: int
    yes_no: int
    signatures: int


class FormInfo(BaseModel):
    """A form, the same for every tenant (its fill status is per tenant, see tenders)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_name: str
    file_format: FileFormat
    # Null while the form's format cannot be parsed yet (it cannot be filled either).
    field_counts: FieldCounts | None


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    section: str
    label: str
    kind: FieldKind
    locator: PdfLocator


class FormDetail(FormInfo):
    tender_id: int
    pages: list[PageSize]
    # In the form's order (reading order).
    fields: list[FieldOut]
