from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.db import SessionDep
from app.modules.knowledge import service
from app.modules.knowledge.schemas import KnowledgeBase
from app.modules.tenants.service import CurrentTenantId

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
def get_knowledge_base(session: SessionDep, tenant_id: CurrentTenantId) -> KnowledgeBase:
    """The current tenant's company documents and their indexing status."""
    return service.get_knowledge_base(session, tenant_id)


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
