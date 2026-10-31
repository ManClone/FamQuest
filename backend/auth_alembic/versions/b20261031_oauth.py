"""Add OAuth clients and authorization codes to central auth database.

Revision ID: b20261031_oauth
Revises: a20261028_auth
"""

import sqlalchemy as sa
from alembic import op

revision = "b20261031_oauth"
down_revision = "a20261028_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("redirect_uri", sa.String(2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column(
            "client_id",
            sa.String(120),
            sa.ForeignKey("oauth_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column("redirect_uri", sa.String(2048), nullable=False),
        sa.Column("code_challenge", sa.String(43), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("oauth_authorization_codes")
    op.drop_table("oauth_clients")
