from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum
from app.modules.filling.rules import AnswerType


class FillStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    READY = "ready"


class ResolvedBy(StrEnum):
    AI = "ai"
    USER = "user"


class AiStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FillEventType(StrEnum):
    PHASE = "phase"
    FIELD = "field"
    DONE = "done"
    ERROR = "error"


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
    # The last AI fill of the form; null when the AI never ran on it.
    ai_status: Mapped[AiStatus | None] = mapped_column(str_enum(AiStatus))
    ai_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Fields the last AI fill could not answer (their model call kept failing): to retry.
    ai_failed_field_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]")
    # Why the last AI fill failed or left fields out, for the user (shown again after a reload).
    ai_error: Mapped[str | None]


class Answer(TimestampMixin, Base):
    """The current answer of a field, in a fill: proposed by the AI or entered by the user."""

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
    # What the automatic fill wrote (null when it never answered), kept when the user changes it.
    proposed_value: Mapped[str | None]
    resolved_by: Mapped[ResolvedBy] = mapped_column(str_enum(ResolvedBy))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # What the AI found (rules.py); null when the AI never answered this field.
    type: Mapped[AnswerType | None] = mapped_column(str_enum(AnswerType))
    # Verified candidates, the selected one first: [{value, citations, source_date, valid_until}].
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    # Why only the user can fill the field (type "manual").
    user_only_reason: Mapped[str | None]
    # The user still has to look at it (missing, manual, conflict, outdated).
    needs_review: Mapped[bool] = mapped_column(default=False, server_default="false")


class FillEvent(TimestampMixin, Base):
    """What the last AI fill of a form did, in order: replayed to the screen (SSE, reload)."""

    __tablename__ = "fill_event"

    # Increasing: also the SSE event id a client resumes from (Last-Event-ID).
    id: Mapped[int] = id_column()
    form_fill_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("form_fill.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[FillEventType] = mapped_column(str_enum(FillEventType))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
