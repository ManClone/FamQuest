"""Revocable opaque MCP token grants (auth DB only)."""

import sqlalchemy as sa
from alembic import op

revision = "c20261031_tokens"
down_revision = "b20261031_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_grants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(120), sa.ForeignKey("oauth_clients.id"), nullable=False),
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("audience", sa.String(2048), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "oauth_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("grant_id", sa.String(64), sa.ForeignKey("oauth_grants.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_tokens_grant_id", "oauth_tokens", ["grant_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_tokens_grant_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_table("oauth_grants")
