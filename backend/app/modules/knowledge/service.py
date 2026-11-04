"""Public API of the knowledge module (other modules only import this file).

A tenant's knowledge base: its company documents, split into passages and indexed for search.
"""

import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.errors import NotFoundError, RuleViolationError
from app.modules.knowledge import index
from app.modules.knowledge.chunking import chunk
from app.modules.knowledge.embedding import Embedder, get_embedder
from app.modules.knowledge.extraction import (
    ExtractedDocument,
    UnreadableDocumentError,
    extract_docx,
    extract_pdf,
)
from app.modules.knowledge.models import Chunk, Document, DocumentFormat, DocumentStatus
from app.modules.knowledge.schemas import DocumentOut, FoundPassage, KnowledgeBase
from app.modules.tenants import service as tenants_service

logger = logging.getLogger(__name__)

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


# Larger files are refused: company documents are certificates, extracts and reports.
MAX_FILE_BYTES = 20 * 1024 * 1024

# Shown when indexing fails for a reason other than an unreadable file.
UNEXPECTED_ERROR = "Something went wrong while reading this file. Try adding it again."


@dataclass(frozen=True)
class NewFile:
    file_name: str
    content: bytes


def add_documents(
    session: Session, tenant_id: int, files: list[NewFile], data_dir: Path
) -> list[DocumentOut]:
    """Store files the user added, as documents to index (status "processing").

    All or nothing: a file of an unsupported format, empty or too large refuses the whole request.
    A file with the name of an existing document replaces it. Indexing is `index_documents`.
    """
    if not files:
        raise RuleViolationError("Add at least one PDF or Word document.")
    for file in files:
        _check_file(file)
    documents = [
        _store(session, tenant_id, Path(file.file_name).name, file.content, data_dir)
        for file in files
    ]
    session.commit()
    return [DocumentOut.model_validate(document) for document in documents]


def index_documents(document_ids: list[int], data_dir: Path) -> None:
    """Extract, split and index stored documents, each in its own transaction (background task).

    Never raises: a document that cannot be indexed ends with status "error" and a message, and
    a document deleted meanwhile is skipped.
    """
    for document_id in document_ids:
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is None:
                continue
            try:
                _index(session, document, (data_dir / document.file_path).read_bytes())
                session.commit()
            except Exception:
                session.rollback()
                document = session.get(Document, document_id)
                if document is None:
                    continue
                logger.exception("Indexing document %s failed", document_id)
                _fail(document, UNEXPECTED_ERROR)
                session.commit()


def delete_document(session: Session, tenant_id: int, document_id: int, data_dir: Path) -> None:
    """Remove a document, its passages and its file: the AI no longer answers from it."""
    document = session.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise NotFoundError(f"Document {document_id} not found")
    folder = (data_dir / document.file_path).parent
    session.delete(document)
    session.commit()
    # After the commit: a failed delete keeps the file the row still points to.
    shutil.rmtree(folder, ignore_errors=True)


def pending_document_ids(session: Session) -> list[int]:
    """Documents left "processing" (the server stopped while indexing them): to index again."""
    return list(
        session.scalars(
            select(Document.id)
            .where(Document.status == DocumentStatus.PROCESSING)
            .order_by(Document.id)
        )
    )


def import_document(
    session: Session,
    tenant_id: int,
    source: Path,
    data_dir: Path,
    embedder: Embedder | None = None,
) -> Document:
    """Store and index a company document from disk, at once (the seed).

    Idempotent on (tenant, file name): a document already indexed is left as is. An unreadable
    file is kept with status "error" and a message for the user.
    """
    document = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.file_name == source.name)
    )
    if document is not None and document.status == DocumentStatus.INDEXED:
        return document
    content = source.read_bytes()
    document = _store(session, tenant_id, source.name, content, data_dir)
    _index(session, document, content, embedder)
    return document


def display_name(file_name: str) -> str:
    """ "01_commercial_register_extract.pdf" → "Commercial register extract"."""
    stem = Path(file_name).stem
    words = re.sub(r"^\d+[\s_-]+", "", stem).replace("_", " ").replace("-", " ").split()
    if not words:
        return stem
    name = " ".join(words)
    return name[0].upper() + name[1:]


def _check_file(file: NewFile) -> None:
    if _format_of(file.file_name) is None:
        raise RuleViolationError(
            f"{Path(file.file_name).name}: only PDF and Word (.docx) documents can be added."
        )
    if not file.content:
        raise RuleViolationError(f"{Path(file.file_name).name} is empty.")
    if len(file.content) > MAX_FILE_BYTES:
        raise RuleViolationError(
            f"{Path(file.file_name).name} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB."
        )


def _format_of(file_name: str) -> DocumentFormat | None:
    try:
        return DocumentFormat(Path(file_name).suffix.lstrip(".").lower())
    except ValueError:
        return None


def _store(
    session: Session, tenant_id: int, file_name: str, content: bytes, data_dir: Path
) -> Document:
    """Write the file and register it "processing"; a document of the same name is replaced."""
    file_format = _format_of(file_name)
    assert file_format is not None, "checked by the caller"
    document = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.file_name == file_name)
    )
    if document is None:
        document = Document(
            tenant_id=tenant_id,
            name=display_name(file_name),
            file_name=file_name,
            file_format=file_format,
            file_path="",
        )
        session.add(document)
        session.flush()
    else:
        # A new version: listed as added now, indexed again from scratch.
        session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        document.created_at = datetime.now(UTC)
        document.status = DocumentStatus.PROCESSING
        document.pages = None
        document.error = None
        document.indexed_at = None
    relative = Path("knowledge") / str(tenant_id) / str(document.id) / file_name
    target = data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    document.file_path = relative.as_posix()
    session.flush()
    return document


def _index(
    session: Session, document: Document, content: bytes, embedder: Embedder | None = None
) -> None:
    try:
        extracted = EXTRACTORS[document.file_format](content)
    except UnreadableDocumentError as error:
        _fail(document, str(error))
        return
    session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    passages = chunk(document.name, extracted.blocks)
    index.store(session, document.id, passages, embedder or get_embedder())
    document.pages = extracted.pages
    document.status = DocumentStatus.INDEXED
    document.error = None
    document.indexed_at = datetime.now(UTC)


def _fail(document: Document, message: str) -> None:
    document.status = DocumentStatus.ERROR
    document.error = message
    document.pages = None
    document.indexed_at = None
