"""A form is shared by every tenant; its answers and status belong to the tenant filling it."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.modules.filling.models import FormFill
from app.modules.tenants import service as tenants_service
from app.modules.tenants.models import Tenant
from tests.modules.helpers import fields_by_key, seeded_forms

ActAs = Callable[[str], AbstractContextManager[None]]


@pytest.fixture
def act_as(client: TestClient) -> Iterator[ActAs]:
    """`with act_as("other"):` sends the requests as another tenant (created on first use)."""

    @contextmanager
    def _act_as(slug: str) -> Iterator[None]:
        with SessionLocal() as session:
            tenant_id = tenants_service.ensure_tenant(session, slug=slug, name=slug.title()).id
            session.commit()
        app.dependency_overrides[tenants_service.get_current_tenant_id] = lambda: tenant_id
        try:
            yield
        finally:
            app.dependency_overrides.pop(tenants_service.get_current_tenant_id)

    yield _act_as
    app.dependency_overrides.pop(tenants_service.get_current_tenant_id, None)


def test_requests_act_for_the_seeded_bidder_by_default(client: TestClient) -> None:
    _, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]

    client.patch(f"/forms/{annex_7['id']}/fields/{telephone['id']}", json={"value": "044"})

    with SessionLocal() as session:
        owners = session.scalars(
            select(Tenant.slug).join(FormFill, FormFill.tenant_id == Tenant.id)
        ).all()
    assert owners == ["alpenlogic"]


def test_two_tenants_fill_the_same_form_without_seeing_each_other(
    client: TestClient, act_as: ActAs
) -> None:
    _, annex_7 = seeded_forms(client)
    fields = fields_by_key(client, annex_7["id"])
    url = f"/forms/{annex_7['id']}/fields/{{}}"

    # Alpenlogic (the default tenant) fills two fields; another bidder fills one, differently.
    client.patch(url.format(fields["telephone"]["id"]), json={"value": "+41 44 512 38 00"})
    client.patch(url.format(fields["e_mail"]["id"]), json={"value": "tenders@alpenlogic.ch"})
    with act_as("helvetia-it"):
        client.patch(url.format(fields["telephone"]["id"]), json={"value": "+41 31 000 00 00"})
        other = client.get(f"/forms/{annex_7['id']}/answers").json()

    mine = client.get(f"/forms/{annex_7['id']}/answers").json()
    assert [a["value"] for a in mine["answers"]] == ["+41 44 512 38 00", "tenders@alpenlogic.ch"]
    assert mine["counts"]["filled"] == 2
    assert [a["value"] for a in other["answers"]] == ["+41 31 000 00 00"]
    assert other["counts"]["filled"] == 1


def test_each_tenant_has_its_own_status_on_the_tender(client: TestClient, act_as: ActAs) -> None:
    _, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]

    client.patch(f"/forms/{annex_7['id']}/fields/{telephone['id']}", json={"value": "044"})

    assert seeded_forms(client)[1]["status"] == "in_review"
    with act_as("helvetia-it"):
        assert seeded_forms(client)[1]["status"] == "not_started"


def test_the_export_only_contains_the_tenants_own_answers(
    client: TestClient, act_as: ActAs
) -> None:
    _, annex_7 = seeded_forms(client)
    telephone = fields_by_key(client, annex_7["id"])["telephone"]
    client.patch(f"/forms/{annex_7['id']}/fields/{telephone['id']}", json={"value": "044"})

    with act_as("helvetia-it"):
        summary = client.get(f"/forms/{annex_7['id']}/export").json()
        exported = client.get(f"/forms/{annex_7['id']}/export/file").content

    mine = client.get(f"/forms/{annex_7['id']}/export/file").content
    assert summary["filled"] == 0
    assert "044" not in _text(exported)
    assert "044" in _text(mine)


def _text(pdf_bytes: bytes) -> str:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        return str(pdf[0].get_text())
