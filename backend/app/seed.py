"""Demo data loaded at startup. Idempotent: running it again changes nothing.

In the real product the tender and its forms come from an external source (tender platform);
here `forms/` at the repo root plays that role.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.forms import service as forms_service
from app.modules.tenants import service as tenants_service
from app.modules.tenders import service as tenders_service

# The bidder company of the demo (docs/USER_FLOW.md), the tenant every request acts for.
TENANT = {"slug": "alpenlogic", "name": "Alpenlogic AG"}

TENDER = {
    "reference": "ZH-2026-0412",
    "title": "Cloud Platform Services – Canton of Zurich",
    "procedure": "Open procedure",
    "authority": "Canton of Zurich, Office for Information Technology",
    "summary": "4-year framework contract · Lots 1 and 2",
    "submission_deadline": date(2026, 11, 19),
}

# (title, file name in seed_forms_dir), in display order.
FORMS = [
    (
        "Annex 4 — Conditions of participation and self-declaration",
        "Annex_4_Conditions of Participation and Company Self-Declaration.docx",
    ),
    (
        "Annex 7 — Sanctions self-declaration (Art. 29c)",
        "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf",
    ),
]


def seed(session: Session, settings: Settings) -> None:
    tenants_service.ensure_tenant(session, **TENANT)
    tender = tenders_service.upsert_tender(session, **TENDER)
    for position, (title, file_name) in enumerate(FORMS):
        forms_service.import_form(
            session,
            tender_id=tender.id,
            position=position,
            title=title,
            source=settings.seed_forms_dir / file_name,
            data_dir=settings.data_dir,
        )
    session.commit()
