"""Central browser sessions, separate from legacy family sessions."""

import sqlalchemy as sa
from alembic import op

revision = "d20261031_sessions"
down_revision = "c20261031_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "browser_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "identity_id",
            sa.Integer(),
            sa.ForeignKey("identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_sessions_identity_id", "browser_sessions", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_browser_sessions_identity_id", table_name="browser_sessions")
    op.drop_table("browser_sessions")
