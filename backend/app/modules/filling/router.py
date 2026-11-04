from fastapi import APIRouter

from app.core.db import SessionDep
from app.modules.filling import service
from app.modules.filling.schemas import AnswerUpdate, FillState
from app.modules.tenants.service import CurrentTenantId

router = APIRouter(prefix="/forms/{form_id}", tags=["filling"])


@router.get("/answers", responses={404: {"description": "Unknown form"}})
def get_answers(form_id: int, session: SessionDep, tenant_id: CurrentTenantId) -> FillState:
    """The current tenant's answers to the form."""
    return service.get_fill_state(session, tenant_id, form_id)


@router.patch(
    "/fields/{field_id}",
    responses={
        404: {"description": "Unknown form or field"},
        422: {"description": "The field cannot be filled (signature, stamp)"},
    },
)
def update_field(
    form_id: int,
    field_id: int,
    body: AnswerUpdate,
    session: SessionDep,
    tenant_id: CurrentTenantId,
) -> FillState:
    """Save the value the user entered. Returns the whole fill state (counts change)."""
    return service.set_answer(session, tenant_id, form_id, field_id, body.value)
