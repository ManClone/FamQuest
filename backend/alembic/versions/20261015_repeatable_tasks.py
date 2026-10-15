"""Allow independently approved repeat task executions with idempotency keys."""

import sqlalchemy as sa
from alembic import op

revision = "d20261015repeat"
down_revision = "c20261014pen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("repeatable", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("task_completions", sa.Column("request_key", sa.String(32), nullable=True))
    op.create_unique_constraint(
        "uq_task_completions_request_key", "task_completions", ["request_key"]
    )
    op.drop_constraint("uq_task_completions_task_id", "task_completions", type_="unique")
    op.create_index(
        "uq_task_completions_single",
        "task_completions",
        ["task_id", "member_id", "date"],
        unique=True,
        postgresql_where=sa.text("request_key IS NULL"),
    )


def downgrade() -> None:
    # Never delete or merge legitimate executions to make an older schema fit.
    duplicates = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM task_completions GROUP BY task_id, member_id, date "
            "HAVING count(*) > 1)"
        )
    )
    if duplicates:
        raise RuntimeError("Repeated task executions exist; restore a compatible backup instead.")
    op.drop_index("uq_task_completions_single", table_name="task_completions")
    op.drop_constraint("uq_task_completions_request_key", "task_completions", type_="unique")
    op.drop_column("task_completions", "request_key")
    op.create_unique_constraint(
        "uq_task_completions_task_id", "task_completions", ["task_id", "member_id", "date"]
    )
    op.drop_column("tasks", "repeatable")
