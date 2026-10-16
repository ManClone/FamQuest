"""Keep original penalties and link their once-only refunds."""

import sqlalchemy as sa
from alembic import op

revision = "h20261016penalty"
down_revision = "g20261016praiserevoke"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "penalty_reversals",
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("point_transactions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "refund_transaction_id",
            sa.Integer(),
            sa.ForeignKey("point_transactions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column(
            "created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    op.drop_table("penalty_reversals")
