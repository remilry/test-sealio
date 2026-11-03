from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from pgvector.psycopg import register_vector
from sqlalchemy import DateTime, create_engine, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _register_vector(dbapi_connection, _connection_record) -> None:
    # The `vector` type only exists once the first migration has run.
    cursor = dbapi_connection.cursor()
    cursor.execute("SELECT 1 FROM pg_type WHERE typname = 'vector'")
    if cursor.fetchone():
        register_vector(dbapi_connection)
    cursor.close()


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """`created_at` / `updated_at` on every table (docs/ARCHITECTURE.md)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
