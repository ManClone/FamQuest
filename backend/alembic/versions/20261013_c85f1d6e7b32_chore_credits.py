"""Track adult XP awards per chore completion.

Revision ID: c85f1d6e7b32
Revises: b74e0c5d6a21
"""
from alembic import op
import sqlalchemy as sa

revision = "c85f1d6e7b32"
down_revision = "b74e0c5d6a21"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chore_credits",
        sa.Column("completion_id", sa.Integer(), sa.ForeignKey("chore_completions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount > 0", name="chore_credit_positive"),
    )


def downgrade():
    op.drop_table("chore_credits")
