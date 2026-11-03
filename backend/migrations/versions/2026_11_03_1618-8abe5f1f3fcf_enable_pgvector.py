"""enable pgvector

Revision ID: 8abe5f1f3fcf
Revises:
Create Date: 2026-11-03 16:18:49.923414

"""

from collections.abc import Sequence

from alembic import op

revision: str = "8abe5f1f3fcf"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
