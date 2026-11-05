"""Development helpers, only answered when `FORMPILOT_DEV_TOOLS` is on (`make dev`)."""

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.errors import NotFoundError
from app.modules.filling import service as filling_service
from app.modules.knowledge import service as knowledge_service
from app.modules.tenants.service import CurrentTenantId

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post(
    "/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Development helpers are off"}},
)
def reset_demo(session: SessionDep, tenant_id: CurrentTenantId) -> None:
    """Back to the start of the demo: no company document, every form "not started" (running
    fills stop). The tender and its forms stay."""
    settings = get_settings()
    if not settings.dev_tools:
        raise NotFoundError("Not found")
    filling_service.discard_all_fills(session, tenant_id)
    knowledge_service.delete_all_documents(session, tenant_id, settings.data_dir)
