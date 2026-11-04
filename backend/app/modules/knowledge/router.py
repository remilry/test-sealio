from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.db import SessionDep
from app.modules.knowledge import service
from app.modules.knowledge.schemas import DocumentOut, KnowledgeBase
from app.modules.tenants.service import CurrentTenantId

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
def get_knowledge_base(session: SessionDep, tenant_id: CurrentTenantId) -> KnowledgeBase:
    """The current tenant's company documents and their indexing status."""
    return service.get_knowledge_base(session, tenant_id)


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    responses={422: {"description": "No file, or a file empty, too large or not PDF/DOCX"}},
)
def add_documents(
    files: Annotated[list[UploadFile], File(description="PDF or Word (.docx) documents")],
    background_tasks: BackgroundTasks,
    session: SessionDep,
    tenant_id: CurrentTenantId,
) -> list[DocumentOut]:
    """Add company documents. They are listed at once as "processing", then indexed in the
    background: poll `GET /knowledge` for their final status ("indexed" or "error")."""
    data_dir = get_settings().data_dir
    documents = service.add_documents(
        session,
        tenant_id,
        [service.NewFile(file.filename or "document", file.file.read()) for file in files],
        data_dir,
    )
    background_tasks.add_task(service.index_documents, [d.id for d in documents], data_dir)
    return documents


@router.get(
    "/documents/{document_id}/file",
    response_class=FileResponse,
    responses={
        200: {"description": "The original company document (PDF or DOCX)."},
        404: {"description": "Unknown document"},
    },
)
def download_document(
    document_id: int, session: SessionDep, tenant_id: CurrentTenantId
) -> FileResponse:
    document_file = service.get_document_file(
        session, tenant_id, document_id, get_settings().data_dir
    )
    return FileResponse(
        document_file.path, media_type=document_file.media_type, filename=document_file.file_name
    )
