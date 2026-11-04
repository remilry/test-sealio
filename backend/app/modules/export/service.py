"""Public API of the export module."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import RuleViolationError
from app.modules.export.pdf_exporter import export_pdf
from app.modules.export.schemas import ExportSummary, FieldRef
from app.modules.filling import service as filling_service
from app.modules.forms import service as forms_service
from app.modules.forms.models import FileFormat
from app.modules.forms.parsing.schema import FieldKind


@dataclass(frozen=True)
class ExportedFile:
    content: bytes
    file_name: str
    media_type: str


def export_summary(session: Session, tenant_id: int, form_id: int) -> ExportSummary:
    form = forms_service.get_form(session, form_id)
    fields = form.fields
    values = filling_service.answer_values(session, tenant_id, form_id)
    fillable = [field for field in fields if field.kind != FieldKind.SIGNATURE]
    return ExportSummary(
        file_format=form.file_format,
        fillable=len(fillable),
        filled=sum(1 for field in fillable if field.id in values),
        empty_fields=[
            FieldRef(id=field.id, label=field.label) for field in fillable if field.id not in values
        ],
        sign_by_hand=[
            FieldRef(id=field.id, label=field.label)
            for field in fields
            if field.kind == FieldKind.SIGNATURE
        ],
    )


def export_file(session: Session, tenant_id: int, form_id: int, data_dir: Path) -> ExportedFile:
    """The original file with the tenant's answers written in, in its original format and layout."""
    form_file = forms_service.get_form_file(session, form_id, data_dir)
    if form_file.file_format != FileFormat.PDF:
        raise RuleViolationError("Export of Word forms is not available yet.")
    values = filling_service.answer_values(session, tenant_id, form_id)
    answers = [
        (field.locator, values[field.id])
        for field in forms_service.list_fields(session, form_id)
        if field.id in values and field.kind != FieldKind.SIGNATURE
    ]
    return ExportedFile(
        content=export_pdf(form_file.path.read_bytes(), answers),
        file_name=form_file.file_name,
        media_type=form_file.media_type,
    )
