"""answer proposed value

Revision ID: b7e4c2d91f30
Revises: a1d52f66eb71
Create Date: 2026-11-05 16:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c2d91f30"
down_revision: str | Sequence[str] | None = "a1d52f66eb71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("answer", sa.Column("proposed_value", sa.String(), nullable=True))
    # Answers still the AI's: what it proposed is their value.
    op.execute("UPDATE answer SET proposed_value = value WHERE resolved_by = 'ai'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("answer", "proposed_value")
