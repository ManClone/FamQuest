"""Adult chore assignment metadata (no automatic XP booking yet).

Revision ID: b74e0c5d6a21
Revises: a63f1d2c4b10
"""

import sqlalchemy as sa
from alembic import op

revision = "b74e0c5d6a21"
down_revision = "a63f1d2c4b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chores",
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=False, server_default="15"),
    )
    op.add_column(
        "chores",
        sa.Column("adult_xp", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "chores",
        sa.Column("assignment_mode", sa.String(12), nullable=False, server_default="flexible"),
    )
    op.add_column(
        "chores",
        sa.Column("fixed_member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_check_constraint("chore_minutes_positive", "chores", "estimated_minutes > 0")
    op.create_check_constraint("chore_xp_nonnegative", "chores", "adult_xp >= 0")
    op.create_check_constraint(
        "chore_assignment_mode_valid", "chores", "assignment_mode IN ('fixed', 'rotate', 'flexible')",
    )


def downgrade():
    op.drop_constraint("chore_assignment_mode_valid", "chores", type_="check")
    op.drop_constraint("chore_xp_nonnegative", "chores", type_="check")
    op.drop_constraint("chore_minutes_positive", "chores", type_="check")
    op.drop_column("chores", "fixed_member_id")
    op.drop_column("chores", "assignment_mode")
    op.drop_column("chores", "adult_xp")
    op.drop_column("chores", "estimated_minutes")
