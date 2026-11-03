"""Business modules. Importing this package registers every model on `Base.metadata` (Alembic)."""

from app.modules.forms import models as _forms_models  # noqa: F401
from app.modules.tenders import models as _tenders_models  # noqa: F401
