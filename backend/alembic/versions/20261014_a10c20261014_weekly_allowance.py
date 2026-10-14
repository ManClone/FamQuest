"""Optional per-child unconditional weekly allowance configuration.

Revision ID: a10c20261014
Revises: f1a20261013b
"""
from alembic import op
import sqlalchemy as sa

revision = "a10c20261014"
down_revision = "f1a20261013b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("family_members", sa.Column("weekly_allowance_cents", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "member_weekly_allowance_positive",
        "family_members",
        "weekly_allowance_cents IS NULL OR (weekly_allowance_cents BETWEEN 1 AND 100000)",
    )


def downgrade() -> None:
    op.drop_constraint("member_weekly_allowance_positive", "family_members", type_="check")
    op.drop_column("family_members", "weekly_allowance_cents")
