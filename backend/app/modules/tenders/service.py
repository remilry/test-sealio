"""Public API of the tenders module (other modules only import this file)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.filling import service as filling_service
from app.modules.forms import service as forms_service
from app.modules.tenders.models import Tender
from app.modules.tenders.schemas import FormSummary, TenderDetail, TenderSummary


def list_tenders(session: Session) -> list[TenderSummary]:
    tenders = session.scalars(select(Tender).order_by(Tender.submission_deadline)).all()
    return [TenderSummary.model_validate(tender) for tender in tenders]


def get_tender(session: Session, tenant_id: int, tender_id: int) -> TenderDetail:
    """The tender with its forms, each with the given tenant's fill status."""
    tender = session.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError(f"Tender {tender_id} not found")
    return TenderDetail(
        **TenderSummary.model_validate(tender).model_dump(),
        procedure=tender.procedure,
        authority=tender.authority,
        summary=tender.summary,
        forms=_forms_with_status(session, tenant_id, tender.id),
    )


def tender_details(session: Session, tender_id: int) -> str:
    """The tender's own information as a text the AI can quote ("Tender details" source)."""
    tender = session.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError(f"Tender {tender_id} not found")
    return "\n".join(
        [
            f"Project title: {tender.title}",
            f"Project number (reference): {tender.reference}",
            f"Contracting authority: {tender.authority}",
            f"Procedure: {tender.procedure}",
            f"Scope: {tender.summary}",
            f"Submission deadline: {tender.submission_deadline:%d %B %Y}",
        ]
    )


def _forms_with_status(session: Session, tenant_id: int, tender_id: int) -> list[FormSummary]:
    forms = forms_service.list_forms(session, tender_id)
    statuses = filling_service.fill_statuses(session, tenant_id, [form.id for form in forms])
    running = filling_service.running_forms(session, tenant_id, [form.id for form in forms])
    return [
        FormSummary(**form.model_dump(), status=statuses[form.id], filling=form.id in running)
        for form in forms
    ]


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
