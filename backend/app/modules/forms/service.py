"""Public API of the forms module (other modules only import this file)."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.forms.models import FileFormat, Form
from app.modules.forms.schemas import FormSummary

MEDIA_TYPES = {
    FileFormat.PDF: "application/pdf",
    FileFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class FormFile:
    path: Path
    file_name: str
    media_type: str


def list_forms(session: Session, tender_id: int) -> list[FormSummary]:
    forms = session.scalars(
        select(Form).where(Form.tender_id == tender_id).order_by(Form.position)
    ).all()
    return [FormSummary.model_validate(form) for form in forms]


def get_form_file(session: Session, form_id: int, data_dir: Path) -> FormFile:
    form = session.get(Form, form_id)
    if form is None:
        raise NotFoundError(f"Form {form_id} not found")
    return FormFile(
        path=data_dir / form.file_path,
        file_name=form.file_name,
        media_type=MEDIA_TYPES[form.file_format],
    )


def import_form(
    session: Session,
    *,
    tender_id: int,
    position: int,
    title: str,
    source: Path,
    data_dir: Path,
) -> Form:
    """Copy an original form file under data_dir and register it.

    Idempotent on (tender, file name): the stored original is never overwritten.
    """
    form = session.scalar(
        select(Form).where(Form.tender_id == tender_id, Form.file_name == source.name)
    )
    if form is None:
        form = Form(
            tender_id=tender_id,
            position=position,
            title=title,
            file_name=source.name,
            file_format=FileFormat(source.suffix.lstrip(".").lower()),
            file_path="",
        )
        session.add(form)
        session.flush()
    relative = Path("forms") / str(form.id) / source.name
    target = data_dir / relative
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    form.file_path = relative.as_posix()
    return form
