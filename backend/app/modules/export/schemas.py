from pydantic import BaseModel

from app.modules.forms.models import FileFormat


class FieldRef(BaseModel):
    id: int
    label: str


class ExportSummary(BaseModel):
    """What the export will contain, and what the user should know before downloading."""

    file_format: FileFormat
    fillable: int
    filled: int
    # Exported blank.
    empty_fields: list[FieldRef]
    # Signatures and stamps: never filled, to sign by hand.
    sign_by_hand: list[FieldRef]
