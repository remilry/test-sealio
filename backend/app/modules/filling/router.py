import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.db import SessionDep, SessionLocal
from app.core.errors import UnavailableError
from app.llm.facade import LLM, LLMError, get_llm
from app.modules.filling import job, service
from app.modules.filling.models import AiStatus, FillEvent
from app.modules.filling.schemas import AiRun, AnswerUpdate, FillState
from app.modules.tenants.service import CurrentTenantId

router = APIRouter(prefix="/forms/{form_id}", tags=["filling"])

# How often the event stream looks for new events of a running fill.
POLL_SECONDS = 0.25


def get_language_model() -> LLM:
    try:
        return get_llm()
    except LLMError as error:
        raise UnavailableError(f"Automatic filling is not available: {error}") from error


LanguageModel = Annotated[LLM, Depends(get_language_model)]


def _fill_of_form(form_id: int, session: SessionDep, tenant_id: CurrentTenantId) -> int | None:
    """The tenant's fill of the form (404 for an unknown form), checked before streaming."""
    service.get_ai_run(session, tenant_id, form_id)
    return service.fill_id_of(session, tenant_id, form_id)


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
    """Save the value the user entered. Returns the whole fill state (counts change).
    Allowed while the form is being filled: the user's value is never replaced."""
    return service.set_answer(session, tenant_id, form_id, field_id, body.value)


@router.post(
    "/fill",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"description": "Unknown form"},
        409: {
            "description": "This form is already being filled, or already filled (discard first)"
        },
        422: {"description": "The form cannot be filled automatically (format not read)"},
        503: {"description": "Automatic filling is not available (no API key)"},
    },
)
def start_fill(
    form_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    tenant_id: CurrentTenantId,
    llm: LanguageModel,
) -> AiRun:
    """Start the automatic fill of the form, in the background: follow it on `GET …/fill/events`.

    Only a form nobody has started can be filled: once it has answers (or a run), they must be
    discarded first (`DELETE …/fill`). A value the user saves during the run is never replaced.
    """
    fill_id = service.start_ai_fill(session, tenant_id, form_id)
    background_tasks.add_task(job.run_fill, fill_id, llm)
    run = service.get_ai_run(session, tenant_id, form_id)
    assert run is not None, "just started"
    return run


@router.delete(
    "/fill",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Unknown form"}},
)
def discard_fill(form_id: int, session: SessionDep, tenant_id: CurrentTenantId) -> None:
    """Discard the fill: every answer (the user's too) and the run are deleted, the form is back
    to "not started". Allowed while it is being filled: that run stops."""
    service.discard_fill(session, tenant_id, form_id)


@router.get(
    "/fill/events",
    response_class=EventSourceResponse,
    responses={404: {"description": "Unknown form"}},
)
async def fill_events(
    fill_id: Annotated[int | None, Depends(_fill_of_form)],
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """The events of the last automatic fill, from the start or after `Last-Event-ID`, then the new
    ones as they happen. Ends with the run ("done" or "error"); empty when no fill ever ran.

    Event types: `phase` ({phase, …}), `field` ({field_id, state: "searching" | "answered",
    answer, counts}), `done` ({filled, fillable, doubts, seconds}), `error` ({message}).
    """
    if fill_id is None:
        return
    after = last_event_id or 0
    while True:
        run_status, events = await asyncio.to_thread(_events_after, fill_id, after)
        for event in events:
            yield ServerSentEvent(data=event.data, event=event.type, id=str(event.id))
            after = event.id
        if run_status != AiStatus.RUNNING:
            return
        await asyncio.sleep(POLL_SECONDS)


def _events_after(fill_id: int, after: int) -> tuple[AiStatus | None, list[FillEvent]]:
    with SessionLocal() as session:
        return service.events_after(session, fill_id, after)
