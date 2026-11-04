from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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
