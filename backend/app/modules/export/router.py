from urllib.parse import quote

from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.core.db import SessionDep
from app.modules.export import service
from app.modules.export.schemas import ExportSummary

router = APIRouter(prefix="/forms/{form_id}/export", tags=["export"])


@router.get("", responses={404: {"description": "Unknown form"}})
def get_export_summary(form_id: int, session: SessionDep) -> ExportSummary:
    return service.export_summary(session, form_id)


@router.get(
    "/file",
    response_class=Response,
    responses={
        200: {"description": "The filled form, in its original format and layout."},
        404: {"description": "Unknown form"},
        422: {"description": "The form's format cannot be exported yet"},
    },
)
def download_filled_form(form_id: int, session: SessionDep) -> Response:
    exported = service.export_file(session, form_id, get_settings().data_dir)
    return Response(
        exported.content,
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(exported.file_name)}"
        },
    )
