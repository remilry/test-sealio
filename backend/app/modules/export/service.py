"""Public API of the export module."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.export.docx_exporter import export_docx
from app.modules.export.pdf_exporter import export_pdf
from app.modules.export.schemas import ExportSummary, FieldRef
from app.modules.filling import service as filling_service
from app.modules.forms import service as forms_service
from app.modules.forms.models import FileFormat
from app.modules.forms.parsing.schema import DocxLocator, FieldKind, PdfLocator


@dataclass(frozen=True)
class ExportedFile:
    content: bytes
    file_name: str
    media_type: str


def export_summary(session: Session, tenant_id: int, form_id: int) -> ExportSummary:
    form = forms_service.get_form(session, form_id)
    fields = form.fields
    answers = {
        answer.field_id: answer
        for answer in filling_service.get_fill_state(session, tenant_id, form_id).answers
    }
    open_fields = filling_service.open_fields(session, tenant_id, form_id)
    fillable = [field for field in fields if field.kind != FieldKind.SIGNATURE]
    filled = [answers[f.id] for f in fillable if f.id in answers and answers[f.id].value]
    by_user = [a for a in answers.values() if a.resolved_by == "user"]
    labels = {field.id: field.label for field in fields}
    return ExportSummary(
        file_format=form.file_format,
        fillable=len(fillable),
        filled=len(filled),
        # Empty fields and doubts nobody settled: a field left empty on purpose is not warned of.
        empty_fields=[FieldRef(id=i, label=labels[i]) for i in open_fields.empty],
        unreviewed_doubts=[FieldRef(id=i, label=labels[i]) for i in open_fields.doubts],
        left_empty=sum(1 for a in by_user if not a.value),
        automatic=sum(1 for a in filled if a.resolved_by == "ai"),
        reviewed=sum(1 for a in by_user if a.value),
        sign_by_hand=[
            FieldRef(id=field.id, label=field.label)
            for field in fields
            if field.kind == FieldKind.SIGNATURE
        ],
    )


def export_file(session: Session, tenant_id: int, form_id: int, data_dir: Path) -> ExportedFile:
    """The original file with the tenant's answers written in, in its original format and layout.
    Signatures are never written."""
    form_file = forms_service.get_form_file(session, form_id, data_dir)
    values = filling_service.answer_values(session, tenant_id, form_id)
    answers = [
        (field.locator, values[field.id])
        for field in forms_service.list_fields(session, form_id)
        if field.id in values and field.kind != FieldKind.SIGNATURE
    ]
    original = form_file.path.read_bytes()
    if form_file.file_format == FileFormat.PDF:
        content = export_pdf(
            original, [(loc, v) for loc, v in answers if isinstance(loc, PdfLocator)]
        )
    else:
        content = export_docx(
            original, [(loc, v) for loc, v in answers if isinstance(loc, DocxLocator)]
        )
    return ExportedFile(
        content=content, file_name=form_file.file_name, media_type=form_file.media_type
    )
