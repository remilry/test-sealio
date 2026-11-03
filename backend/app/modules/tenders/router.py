from fastapi import APIRouter

from app.core.db import SessionDep
from app.modules.tenders import service
from app.modules.tenders.schemas import TenderDetail, TenderSummary

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("")
def list_tenders(session: SessionDep) -> list[TenderSummary]:
    return service.list_tenders(session)


@router.get("/{tender_id}", responses={404: {"description": "Unknown tender"}})
def get_tender(tender_id: int, session: SessionDep) -> TenderDetail:
    return service.get_tender(session, tender_id)
