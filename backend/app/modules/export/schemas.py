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
    # Exported blank, and nobody chose to leave them empty.
    empty_fields: list[FieldRef]
    # Values still to check (conflict, outdated, unsure, suggested): exported as they are.
    unreviewed_doubts: list[FieldRef]
    # Left empty by the user on purpose.
    left_empty: int
    # Filled automatically, kept without review.
    automatic: int
    # Settled by the user with a value (kept, chosen or entered).
    reviewed: int
    # Signatures and stamps: never filled, to sign by hand.
    sign_by_hand: list[FieldRef]
