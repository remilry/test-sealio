from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum
from app.modules.forms.parsing.schema import FieldKind


class FileFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class Form(TimestampMixin, Base):
    """A buyer form to fill, attached to a tender. Shared by every tenant: each fills it in its own
    `form_fill`. The original file is kept untouched on disk."""

    __tablename__ = "form"
    __table_args__ = (
        # (tender_id, position) also serves the foreign-key lookups: no separate tender_id index.
        UniqueConstraint("tender_id", "position"),
        UniqueConstraint("tender_id", "file_name"),
    )

    id: Mapped[int] = id_column()
    tender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tender.id", ondelete="CASCADE"))
    position: Mapped[int]
    title: Mapped[str]
    file_name: Mapped[str]
    file_format: Mapped[FileFormat] = mapped_column(str_enum(FileFormat))
    # Relative to settings.data_dir.
    file_path: Mapped[str]
    # Set once the file has been parsed into fields; null while its format has no parser yet.
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Page sizes in points ([{width, height}]), for the preview overlay.
    pages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")


class Field(TimestampMixin, Base):
    """A blank of a form to fill, as detected by the parser."""

    __tablename__ = "field"
    __table_args__ = (
        # (form_id, position) also serves the foreign-key lookups: no separate form_id index.
        UniqueConstraint("form_id", "position"),
        UniqueConstraint("form_id", "key"),
    )

    id: Mapped[int] = id_column()
    form_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("form.id", ondelete="CASCADE"))
    position: Mapped[int]
    key: Mapped[str]
    section: Mapped[str]
    label: Mapped[str]
    kind: Mapped[FieldKind] = mapped_column(str_enum(FieldKind))
    # Where the answer goes in the original file (PdfLocator for now), see parsing/schema.py.
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB)
