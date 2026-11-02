"""Audited family suspension; registry only, no family schema changes."""

import sqlalchemy as sa
from alembic import op

revision = "g20261101_status"
down_revision = "f20261101_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_identity_id",
            sa.Integer(),
            sa.ForeignKey("identities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("family_name", sa.String(100), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("actor_identity_id", "request_key"),
    )
    op.create_index("ix_tenant_status_events_tenant_id", "tenant_status_events", ["tenant_id"])


def downgrade() -> None:
    # Revocation is intentionally not undone by removing the audit schema.
    op.drop_index("ix_tenant_status_events_tenant_id", table_name="tenant_status_events")
    op.drop_table("tenant_status_events")
