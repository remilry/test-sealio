"""An unexpected error never reaches the user as a trace: a plain message, the details logged."""

import logging

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import GENERIC_ERROR
from app.main import app

router = APIRouter()


@router.get("/__test__/crash")
def crash() -> None:
    raise RuntimeError("secret internals")


app.include_router(router)


def test_an_unexpected_error_returns_a_plain_500(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.ERROR),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/__test__/crash")

    assert response.status_code == 500
    assert response.json() == {"detail": GENERIC_ERROR}
    assert GENERIC_ERROR == "Something went wrong on our side. Please try again in a moment."
    assert "secret internals" not in response.text
    assert "secret internals" in caplog.text
    assert "Traceback" in caplog.text


def test_the_plain_500_reaches_the_browser_of_the_front() -> None:
    # Without the CORS header the browser hides the response: the front would only see a
    # network failure, never the message.
    origin = get_settings().cors_origins[0]
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/crash", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.json() == {"detail": GENERIC_ERROR}
