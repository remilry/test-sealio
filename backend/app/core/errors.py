from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    """Raised by services when an entity does not exist; rendered as HTTP 404."""


class RuleViolationError(Exception):
    """Raised by services when a request breaks a business rule; rendered as HTTP 422."""


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RuleViolationError)
    async def _rule_violation(_request: Request, exc: RuleViolationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
