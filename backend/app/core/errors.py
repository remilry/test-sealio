import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Any unexpected error, as the user reads it (the details go to the logs).
GENERIC_ERROR = "Something went wrong on our side. Please try again in a moment."


class NotFoundError(Exception):
    """Raised by services when an entity does not exist; rendered as HTTP 404."""


class RuleViolationError(Exception):
    """Raised by services when a request breaks a business rule; rendered as HTTP 422."""


class ConflictError(Exception):
    """Raised by services when the request clashes with work in progress; rendered as HTTP 409."""


class UnavailableError(Exception):
    """Raised when a service the request needs is not available; rendered as HTTP 503."""


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(UnavailableError)
    async def _unavailable(_request: Request, exc: UnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RuleViolationError)
    async def _rule_violation(_request: Request, exc: RuleViolationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unexpected error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": GENERIC_ERROR})
