"""Public API of the tenants module (other modules only import this file)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionDep
from app.modules.tenants.models import Tenant


def ensure_tenant(session: Session, *, slug: str, name: str) -> Tenant:
    """Create the tenant, or update its name when its slug already exists."""
    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = Tenant(slug=slug)
        session.add(tenant)
    tenant.name = name
    session.flush()
    return tenant


def get_current_tenant_id(session: SessionDep) -> int:
    """The tenant of the request.

    No login in this version: every request acts for the configured tenant. With real
    authentication, this is the only place to change (read the tenant from the user's token).
    """
    slug = get_settings().current_tenant
    tenant_id = session.scalar(select(Tenant.id).where(Tenant.slug == slug))
    if tenant_id is None:
        raise RuntimeError(f"Tenant {slug!r} does not exist: it is created by the seed at startup.")
    return tenant_id


CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]
