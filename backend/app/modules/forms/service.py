"""Public API of the forms module (other modules only import this file)."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.modules.forms.models import Field, FileFormat, Form
from app.modules.forms.parsing.pdf_parser import parse_pdf
from app.modules.forms.parsing.schema import FieldKind, FormSchema, PageSize
from app.modules.forms.schemas import FieldCounts, FieldOut, FormDetail, FormInfo

MEDIA_TYPES = {
    FileFormat.PDF: "application/pdf",
    FileFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Formats that can be parsed into fields. Word forms come with step 7 (docs/PLAN.md).
PARSERS: dict[FileFormat, Callable[[bytes], FormSchema]] = {FileFormat.PDF: parse_pdf}


@dataclass(frozen=True)
class FormFile:
    path: Path
    file_name: str
    file_format: FileFormat
    media_type: str


def list_forms(session: Session, tender_id: int) -> list[FormInfo]:
    forms = session.scalars(
        select(Form).where(Form.tender_id == tender_id).order_by(Form.position)
    ).all()
    form_ids = [form.id for form in forms]
    counts, sections = _field_counts(session, form_ids), _section_counts(session, form_ids)
    return [_summary(form, counts, sections) for form in forms]


def get_form(session: Session, form_id: int) -> FormDetail:
    form = _get(session, form_id)
    return FormDetail(
        **_summary(
            form, _field_counts(session, [form.id]), _section_counts(session, [form.id])
        ).model_dump(),
        tender_id=form.tender_id,
        pages=[PageSize.model_validate(page) for page in form.pages],
        fields=list_fields(session, form_id),
    )


def list_fields(session: Session, form_id: int) -> list[FieldOut]:
    """Fields of a form in reading order. Raises NotFoundError for an unknown form."""
    _get(session, form_id)
    fields = session.scalars(
        select(Field).where(Field.form_id == form_id).order_by(Field.position)
    ).all()
    return [FieldOut.model_validate(field) for field in fields]


def get_field(session: Session, form_id: int, field_id: int) -> FieldOut:
    field = session.get(Field, field_id)
    if field is None or field.form_id != form_id:
        raise NotFoundError(f"Field {field_id} not found in form {form_id}")
    return FieldOut.model_validate(field)


def get_form_file(session: Session, form_id: int, data_dir: Path) -> FormFile:
    form = _get(session, form_id)
    return FormFile(
        path=data_dir / form.file_path,
        file_name=form.file_name,
        file_format=form.file_format,
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
    """Copy an original form file under data_dir, register it and parse its fields.

    Idempotent on (tender, file name): the stored original is never overwritten, and a form is
    parsed once (a form imported before its format had a parser is parsed on the next import).
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
    parser = PARSERS.get(form.file_format)
    if form.parsed_at is None and parser is not None:
        _store_schema(session, form, parser(target.read_bytes()))
    return form


def _store_schema(session: Session, form: Form, schema: FormSchema) -> None:
    form.pages = [page.model_dump() for page in schema.pages]
    for position, parsed in enumerate(schema.fields):
        session.add(
            Field(
                form_id=form.id,
                position=position,
                key=parsed.key,
                section=parsed.section,
                label=parsed.label,
                kind=parsed.kind,
                locator=parsed.locator.model_dump(),
            )
        )
    form.parsed_at = datetime.now(UTC)


def _get(session: Session, form_id: int) -> Form:
    form = session.get(Form, form_id)
    if form is None:
        raise NotFoundError(f"Form {form_id} not found")
    return form


def _field_counts(session: Session, form_ids: list[int]) -> dict[int, dict[FieldKind, int]]:
    rows = session.execute(
        select(Field.form_id, Field.kind, func.count())
        .where(Field.form_id.in_(form_ids))
        .group_by(Field.form_id, Field.kind)
    ).all()
    counts: dict[int, dict[FieldKind, int]] = {}
    for form_id, kind, count in rows:
        counts.setdefault(form_id, {})[kind] = count
    return counts


def _section_counts(session: Session, form_ids: list[int]) -> dict[int, int]:
    rows = session.execute(
        select(Field.form_id, func.count(func.distinct(Field.section)))
        .where(Field.form_id.in_(form_ids))
        .group_by(Field.form_id)
    ).all()
    return dict(rows)


def _summary(
    form: Form, counts: dict[int, dict[FieldKind, int]], sections: dict[int, int]
) -> FormInfo:
    by_kind = counts.get(form.id, {})
    return FormInfo(
        id=form.id,
        title=form.title,
        file_name=form.file_name,
        file_format=form.file_format,
        field_counts=None
        if form.parsed_at is None
        else FieldCounts(
            fields=sum(by_kind.values()),
            yes_no=by_kind.get(FieldKind.YES_NO, 0),
            signatures=by_kind.get(FieldKind.SIGNATURE, 0),
        ),
        estimated_fill_seconds=None
        if form.parsed_at is None
        else sections.get(form.id, 0) * get_settings().fill_seconds_per_section,
    )
