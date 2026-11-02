"""Operator family creation reservations, independent of family schemas."""

import sqlalchemy as sa
from alembic import op

revision = "h20261102_creation"
down_revision = "g20261101_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_creations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "actor_identity_id",
            sa.Integer(),
            sa.ForeignKey("identities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "parent_identity_id",
            sa.Integer(),
            sa.ForeignKey("identities.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("family_name", sa.String(100), nullable=False),
        sa.Column("parent_name", sa.String(50), nullable=False),
        sa.Column("parent_email", sa.String(254), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("actor_identity_id", "request_key"),
    )


def downgrade() -> None:
    # Never undo family data or credentials when removing this metadata table.
    op.drop_table("family_creations")
