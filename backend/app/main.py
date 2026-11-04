import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionDep, SessionLocal
from app.core.errors import register_error_handlers
from app.core.migrations import upgrade_to_head
from app.modules.export.router import router as export_router
from app.modules.filling import service as filling_service
from app.modules.filling.router import router as filling_router
from app.modules.forms.router import router as forms_router
from app.modules.knowledge import service as knowledge_service
from app.modules.knowledge.router import router as knowledge_router
from app.modules.tenders.router import router as tenders_router
from app.seed import seed


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        seed(session, settings)
        filling_service.fail_interrupted_fills(session)
        pending = knowledge_service.pending_document_ids(session)
    # Documents the server stopped indexing: indexed again without delaying startup.
    resume = asyncio.create_task(
        asyncio.to_thread(knowledge_service.index_documents, pending, settings.data_dir)
    )
    yield
    await resume


app = FastAPI(title="Formpilot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(tenders_router)
app.include_router(forms_router)
app.include_router(filling_router)
app.include_router(export_router)
app.include_router(knowledge_router)


class Health(BaseModel):
    status: str
    database: str


@app.get("/health", tags=["system"])
def health(session: SessionDep) -> Health:
    session.execute(text("SELECT 1"))
    return Health(status="ok", database="ok")
