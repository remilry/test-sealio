from pydantic import BaseModel, ConfigDict

from app.modules.forms.models import FileFormat, FormStatus


class FormSummary(BaseModel):
    """A form as listed on its tender page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_name: str
    file_format: FileFormat
    status: FormStatus
