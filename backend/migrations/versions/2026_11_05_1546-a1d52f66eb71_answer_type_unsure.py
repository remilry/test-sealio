"""answer type unsure

Revision ID: a1d52f66eb71
Revises: cada875d6f07
Create Date: 2026-11-05 15:46:14.964204

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1d52f66eb71"
down_revision: str | Sequence[str] | None = "cada875d6f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TYPES = ("auto", "missing", "manual", "outdated", "conflict", "declaration")


def _check(types: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_answer_answertype"), "answer", type_="check")
    values = ", ".join(f"'{t}'" for t in types)
    op.create_check_constraint(op.f("ck_answer_answertype"), "answer", f"type IN ({values})")


def upgrade() -> None:
    """A value only one of two runs found: "unsure"."""
    _check((*TYPES, "unsure"))


def downgrade() -> None:
    op.execute("UPDATE answer SET type = 'auto' WHERE type = 'unsure'")
    _check(TYPES)
