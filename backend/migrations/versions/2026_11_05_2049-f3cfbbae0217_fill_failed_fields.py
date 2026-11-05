"""fill failed fields

Revision ID: f3cfbbae0217
Revises: b7e4c2d91f30
Create Date: 2026-11-05 20:49:23.540931

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3cfbbae0217"
down_revision: str | Sequence[str] | None = "b7e4c2d91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fields the last AI fill could not answer, and its message for the user."""
    op.add_column(
        "form_fill",
        sa.Column(
            "ai_failed_field_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column("form_fill", sa.Column("ai_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("form_fill", "ai_error")
    op.drop_column("form_fill", "ai_failed_field_ids")
