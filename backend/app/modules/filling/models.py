from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum


class FillStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    READY = "ready"


class ResolvedBy(StrEnum):
    AI = "ai"
    USER = "user"


class FormFill(TimestampMixin, Base):
    """A tenant's work on a form: the form (and its fields) is shared, the fill is the tenant's.

    Several tenants fill the same form; within a tenant, colleagues share one fill. Created with
    the first answer: no row means not started.
    """

    __tablename__ = "form_fill"
    __table_args__ = (
        # (tenant_id, form_id) also serves the tenant's lookups: no separate tenant_id index.
        UniqueConstraint("tenant_id", "form_id"),
    )

    id: Mapped[int] = id_column()
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenant.id", ondelete="CASCADE"))
    form_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("form.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[FillStatus] = mapped_column(
        str_enum(FillStatus), default=FillStatus.NOT_STARTED, server_default=FillStatus.NOT_STARTED
    )


class Answer(TimestampMixin, Base):
    """The current answer of a field, in a fill. Step 4.5: entered by hand; AI columns at step 5."""

    __tablename__ = "answer"
    __table_args__ = (
        # One answer per field and fill; also serves the fill's lookups.
        UniqueConstraint("form_fill_id", "field_id"),
    )

    id: Mapped[int] = id_column()
    form_fill_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("form_fill.id", ondelete="CASCADE")
    )
    # Indexed for the cascade when a field is deleted.
    field_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("field.id", ondelete="CASCADE"), index=True
    )
    # Null: the field is left empty.
    value: Mapped[str | None]
    resolved_by: Mapped[ResolvedBy] = mapped_column(str_enum(ResolvedBy))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
