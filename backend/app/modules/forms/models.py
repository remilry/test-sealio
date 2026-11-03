from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum


class FileFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class FormStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    READY = "ready"


class Form(TimestampMixin, Base):
    """A buyer form to fill, attached to a tender. The original file is kept untouched on disk."""

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
    status: Mapped[FormStatus] = mapped_column(
        str_enum(FormStatus), default=FormStatus.NOT_STARTED, server_default=FormStatus.NOT_STARTED
    )
