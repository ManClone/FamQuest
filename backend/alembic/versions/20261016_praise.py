"""Add immutable praise hearts without changing star balances or XP."""

import sqlalchemy as sa
from alembic import op

revision = "f20261016praise"
down_revision = "e20261016chores"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "praises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("family_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_praises_member_id", "praises", ["member_id"])


def downgrade():
    op.drop_index("ix_praises_member_id", table_name="praises")
    op.drop_table("praises")
