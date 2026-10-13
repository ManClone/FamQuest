"""Separate monetary earnings ledger and per-task rewards.

Revision ID: e07a3b9c5d22
Revises: d96f2e8a4c10
"""
from alembic import op
import sqlalchemy as sa

revision = "e07a3b9c5d22"
down_revision = "d96f2e8a4c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("money_cents", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("tasks_money_nonnegative", "tasks", "money_cents >= 0")
    op.add_column("task_completions", sa.Column("money_cents", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("completion_money_nonnegative", "task_completions", "money_cents >= 0")
    op.create_table(
        "money_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("completion_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_cents <> 0", name="money_amount_nonzero"),
    )


def downgrade() -> None:
    op.drop_table("money_transactions")
    op.drop_constraint("completion_money_nonnegative", "task_completions", type_="check")
    op.drop_column("task_completions", "money_cents")
    op.drop_constraint("tasks_money_nonnegative", "tasks", type_="check")
    op.drop_column("tasks", "money_cents")
