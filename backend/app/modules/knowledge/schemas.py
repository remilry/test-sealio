from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.knowledge.models import DocumentFormat, DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    file_name: str
    file_format: DocumentFormat
    # Null for Word documents (no fixed pages).
    pages: int | None
    status: DocumentStatus
    # Why the file could not be indexed (status "error").
    error: str | None
    # When the document was added.
    created_at: datetime
    indexed_at: datetime | None


class KnowledgeBase(BaseModel):
    """What the AI answers from, for the current tenant."""

    company_name: str
    # Newest first.
    documents: list[DocumentOut]
    # When the last document was indexed; null when none is.
    last_indexed_at: datetime | None


class FoundPassage(BaseModel):
    """A search result: a passage and where it comes from."""

    chunk_id: int
    document_id: int
    document_name: str
    page: int | None
    text: str
    # Fused rank score (higher is better), comparable within one search only.
    score: float
