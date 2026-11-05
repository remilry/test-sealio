import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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

    # Not an exception handler for Exception: Starlette runs that one outside every middleware,
    # so the 500 would lose its CORS headers and the browser would hide it. Must be added before
    # CORSMiddleware (the last middleware added is the outermost).
    app.add_middleware(_UnexpectedErrors)


class _UnexpectedErrors:
    """Any exception a route lets through: logged with its trace, answered with a plain 500
    (unless the response had already started, e.g. a stream: then the connection just ends)."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = False

        async def watch(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self._app(scope, receive, watch)
        except Exception:
            logger.exception("Unexpected error on %s %s", scope["method"], scope["path"])
            if started:
                raise
            response = JSONResponse(status_code=500, content={"detail": GENERIC_ERROR})
            await response(scope, receive, send)
