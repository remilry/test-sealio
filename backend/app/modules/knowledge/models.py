from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Computed, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, id_column, str_enum
from app.modules.knowledge.embedding import DIMENSIONS


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    INDEXED = "indexed"
    ERROR = "error"


class Document(TimestampMixin, Base):
    """A company document the AI answers from. Belongs to a tenant (its knowledge base)."""

    __tablename__ = "document"
    __table_args__ = (
        # Also serves the tenant's lookups: no separate tenant_id index.
        UniqueConstraint("tenant_id", "file_name"),
    )

    id: Mapped[int] = id_column()
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenant.id", ondelete="CASCADE"))
    # Display name ("Commercial register extract").
    name: Mapped[str]
    file_name: Mapped[str]
    file_format: Mapped[DocumentFormat] = mapped_column(str_enum(DocumentFormat))
    # Relative to settings.data_dir.
    file_path: Mapped[str]
    # Null for Word documents (no fixed pages) and while processing.
    pages: Mapped[int | None]
    status: Mapped[DocumentStatus] = mapped_column(
        str_enum(DocumentStatus),
        default=DocumentStatus.PROCESSING,
        server_default=DocumentStatus.PROCESSING,
    )
    # Why the file could not be indexed, for the user.
    error: Mapped[str | None]
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Chunk(TimestampMixin, Base):
    """A passage of a document: what the search returns and the AI cites."""

    __tablename__ = "chunk"
    __table_args__ = (
        # (document_id, position) also serves the foreign-key lookups.
        UniqueConstraint("document_id", "position"),
        Index(
            "ix_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = id_column()
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE")
    )
    position: Mapped[int]
    # 0-based; null for Word documents.
    page: Mapped[int | None]
    # Rectangle of the passage on its page (PDF only), see extraction/blocks.py Box.
    box: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Verbatim text: citations are checked against it.
    text: Mapped[str]
    # Document title and section heading, searched with the text but never cited.
    context: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', context || ' ' || text)", persisted=True),
    )
