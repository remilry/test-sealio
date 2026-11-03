from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum


class ResolvedBy(StrEnum):
    AI = "ai"
    USER = "user"


class Answer(TimestampMixin, Base):
    """The current answer of a field. Step 4.5: entered by hand; AI columns come with step 5."""

    __tablename__ = "answer"

    id: Mapped[int] = id_column()
    # One answer per field; the unique constraint also indexes the foreign key.
    field_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("field.id", ondelete="CASCADE"), unique=True
    )
    # Null: the field is left empty.
    value: Mapped[str | None]
    resolved_by: Mapped[ResolvedBy] = mapped_column(str_enum(ResolvedBy))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
