from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.db import SessionDep
from app.modules.forms import service

router = APIRouter(prefix="/forms", tags=["forms"])


@router.get(
    "/{form_id}/file",
    response_class=FileResponse,
    responses={200: {"description": "The original form file (PDF or DOCX), untouched."}},
)
def download_original_form(form_id: int, session: SessionDep) -> FileResponse:
    form_file = service.get_form_file(session, form_id, get_settings().data_dir)
    return FileResponse(
        form_file.path, media_type=form_file.media_type, filename=form_file.file_name
    )
