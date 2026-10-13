"""Persist confirmed weekly adult chore assignments.

Revision ID: d96f2e8a4c10
Revises: c85f1d6e7b32
"""
from alembic import op
import sqlalchemy as sa

revision = "d96f2e8a4c10"
down_revision = "c85f1d6e7b32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_chore_assignments",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("chore_id", sa.Integer(), sa.ForeignKey("chores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("week_start", "chore_id"),
    )


def downgrade() -> None:
    op.drop_table("weekly_chore_assignments")
