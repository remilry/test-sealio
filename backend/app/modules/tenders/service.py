"""Public API of the tenders module (other modules only import this file)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.forms import service as forms_service
from app.modules.tenders.models import Tender
from app.modules.tenders.schemas import TenderDetail, TenderSummary


def list_tenders(session: Session) -> list[TenderSummary]:
    tenders = session.scalars(select(Tender).order_by(Tender.submission_deadline)).all()
    return [TenderSummary.model_validate(tender) for tender in tenders]


def get_tender(session: Session, tender_id: int) -> TenderDetail:
    tender = session.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError(f"Tender {tender_id} not found")
    return TenderDetail(
        **TenderSummary.model_validate(tender).model_dump(),
        procedure=tender.procedure,
        authority=tender.authority,
        summary=tender.summary,
        forms=forms_service.list_forms(session, tender.id),
    )


def upsert_tender(
    session: Session,
    *,
    reference: str,
    title: str,
    procedure: str,
    authority: str,
    summary: str,
    submission_deadline: date,
) -> Tender:
    """Create the tender, or update it in place when its reference already exists."""
    tender = session.scalar(select(Tender).where(Tender.reference == reference))
    if tender is None:
        tender = Tender(reference=reference)
        session.add(tender)
    tender.title = title
    tender.procedure = procedure
    tender.authority = authority
    tender.summary = summary
    tender.submission_deadline = submission_deadline
    session.flush()
    return tender
