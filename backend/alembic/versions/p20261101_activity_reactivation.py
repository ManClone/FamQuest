"""Retain reversible activity snapshots without rewriting monetary/point journals."""

import sqlalchemy as sa
from alembic import op

revision = "p20261101reactivate"
down_revision = "o20261101links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("origin_id", sa.Integer(), nullable=False),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("family_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(100)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("inactive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("restored_at", sa.DateTime(timezone=True)),
        sa.Column(
            "changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.UniqueConstraint(
            "source", "origin_id", "member_id", name="uq_activity_correction_origin"
        ),
    )
    op.create_index("ix_activity_corrections_member_id", "activity_corrections", ["member_id"])
    op.create_table(
        "activity_journal_links",
        sa.Column("journal_source", sa.String(10), primary_key=True),
        sa.Column("journal_id", sa.Integer(), primary_key=True),
        sa.Column(
            "correction_id",
            sa.Integer(),
            sa.ForeignKey("activity_corrections.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_activity_journal_links_correction_id", "activity_journal_links", ["correction_id"]
    )


def downgrade() -> None:
    op.drop_table("activity_journal_links")
    op.drop_table("activity_corrections")
