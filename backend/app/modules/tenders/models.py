from datetime import date

from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column


class Tender(TimestampMixin, Base):
    """A call for tenders. Also a source for the AI ("Tender details")."""

    __tablename__ = "tender"

    id: Mapped[int] = id_column()
    reference: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    procedure: Mapped[str]
    authority: Mapped[str]
    summary: Mapped[str]
    submission_deadline: Mapped[date]
