"""Separate central operator sessions; no family schema changes."""

import sqlalchemy as sa
from alembic import op

revision = "f20261101_operator"
down_revision = "e20261031_actors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "identity_id",
            sa.Integer(),
            sa.ForeignKey("identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operator_sessions_identity_id", "operator_sessions", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_operator_sessions_identity_id", table_name="operator_sessions")
    op.drop_table("operator_sessions")
