"""Public API of the knowledge module (other modules only import this file).

A tenant's knowledge base: its company documents, split into passages and indexed for search.
"""

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.knowledge import index
from app.modules.knowledge.chunking import chunk
from app.modules.knowledge.embedding import Embedder, get_embedder
from app.modules.knowledge.extraction import (
    ExtractedDocument,
    UnreadableDocumentError,
    extract_docx,
    extract_pdf,
)
from app.modules.knowledge.models import Document, DocumentFormat, DocumentStatus
from app.modules.knowledge.schemas import DocumentOut, FoundPassage, KnowledgeBase
from app.modules.tenants import service as tenants_service

MEDIA_TYPES = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

EXTRACTORS: dict[DocumentFormat, Callable[[bytes], ExtractedDocument]] = {
    DocumentFormat.PDF: extract_pdf,
    DocumentFormat.DOCX: extract_docx,
}


@dataclass(frozen=True)
class DocumentFile:
    path: Path
    file_name: str
    media_type: str


def get_knowledge_base(session: Session, tenant_id: int) -> KnowledgeBase:
    documents = session.scalars(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return KnowledgeBase(
        company_name=tenants_service.get_tenant_name(session, tenant_id),
        documents=[DocumentOut.model_validate(document) for document in documents],
        last_indexed_at=session.scalar(
            select(func.max(Document.indexed_at)).where(Document.tenant_id == tenant_id)
        ),
    )


def search(
    session: Session, tenant_id: int, query: str, k: int = 8, embedder: Embedder | None = None
) -> list[FoundPassage]:
    """The k passages of the tenant's indexed documents that best match the query."""
    return index.search(session, tenant_id, query, embedder or get_embedder(), k)


def get_document_file(
    session: Session, tenant_id: int, document_id: int, data_dir: Path
) -> DocumentFile:
    document = session.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise NotFoundError(f"Document {document_id} not found")
    return DocumentFile(
        path=data_dir / document.file_path,
        file_name=document.file_name,
        media_type=MEDIA_TYPES[document.file_format],
    )


def import_document(
    session: Session,
    tenant_id: int,
    source: Path,
    data_dir: Path,
    embedder: Embedder | None = None,
) -> Document:
    """Copy a company document under data_dir, then extract, split and index it.

    Idempotent on (tenant, file name): a document already indexed is left as is. An unreadable
    file is kept with status "error" and a message for the user.
    """
    document = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.file_name == source.name)
    )
    if document is not None and document.status == DocumentStatus.INDEXED:
        return document
    if document is None:
        document = Document(
            tenant_id=tenant_id,
            name=display_name(source.name),
            file_name=source.name,
            file_format=DocumentFormat(source.suffix.lstrip(".").lower()),
            file_path="",
        )
        session.add(document)
        session.flush()
    relative = Path("knowledge") / str(tenant_id) / str(document.id) / source.name
    target = data_dir / relative
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    document.file_path = relative.as_posix()
    _index(session, document, target.read_bytes(), embedder or get_embedder())
    return document


def display_name(file_name: str) -> str:
    """ "01_commercial_register_extract.pdf" → "Commercial register extract"."""
    stem = Path(file_name).stem
    words = re.sub(r"^\d+[\s_-]+", "", stem).replace("_", " ").replace("-", " ").split()
    if not words:
        return stem
    name = " ".join(words)
    return name[0].upper() + name[1:]


def _index(session: Session, document: Document, content: bytes, embedder: Embedder) -> None:
    try:
        extracted = EXTRACTORS[document.file_format](content)
    except UnreadableDocumentError as error:
        document.status = DocumentStatus.ERROR
        document.error = str(error)
        return
    index.store(session, document.id, chunk(document.name, extracted.blocks), embedder)
    document.pages = extracted.pages
    document.status = DocumentStatus.INDEXED
    document.error = None
    document.indexed_at = datetime.now(UTC)
