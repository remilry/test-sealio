from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column


class Tenant(TimestampMixin, Base):
    """A bidder company: owns its knowledge base and its fills of the tender forms."""

    __tablename__ = "tenant"

    id: Mapped[int] = id_column()
    # Stable identifier (the seed and, later, the identity provider refer to it).
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
