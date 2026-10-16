"""Allow independent household executions while preserving legacy daily requests."""

import sqlalchemy as sa
from alembic import op

revision = "e20261016chores"
down_revision = "d20261015repeat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chore_completions", sa.Column("request_key", sa.String(32), nullable=True))
    op.create_unique_constraint(
        "uq_chore_completions_request_key", "chore_completions", ["request_key"]
    )
    op.drop_constraint("uq_chore_completions_chore_id", "chore_completions", type_="unique")
    op.create_index(
        "uq_chore_completions_single",
        "chore_completions",
        ["chore_id", "date"],
        unique=True,
        postgresql_where=sa.text("request_key IS NULL"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM chore_completions "
            "GROUP BY chore_id, date HAVING count(*) > 1)"
        )
    ):
        raise RuntimeError(
            "Repeated household executions exist; restore a compatible backup instead."
        )
    op.drop_index("uq_chore_completions_single", table_name="chore_completions")
    op.drop_constraint("uq_chore_completions_request_key", "chore_completions", type_="unique")
    op.drop_column("chore_completions", "request_key")
    op.create_unique_constraint(
        "uq_chore_completions_chore_id", "chore_completions", ["chore_id", "date"]
    )
