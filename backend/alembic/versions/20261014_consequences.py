"""Consequence presets and auditable penalty events.

Revision ID: c20261014pen
Revises: 5ec074ee95f5
"""

from alembic import op
import sqlalchemy as sa

revision = "c20261014pen"
down_revision = "5ec074ee95f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consequence_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(100), nullable=False, unique=True),
        sa.Column("money_penalty_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp_penalty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("money_penalty_cents >= 0", name="consequence_preset_money_nonnegative"),
        sa.CheckConstraint("xp_penalty >= 0", name="consequence_preset_xp_nonnegative"),
    )
    op.create_table(
        "consequence_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preset_id", sa.Integer(), sa.ForeignKey("consequence_presets.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("money_penalty_cents", sa.Integer(), nullable=False),
        sa.Column("xp_penalty_requested", sa.Integer(), nullable=False),
        sa.Column("xp_penalty_applied", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reversal_note", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("money_penalty_cents >= 0", name="consequence_entry_money_nonnegative"),
        sa.CheckConstraint("xp_penalty_requested >= 0", name="consequence_entry_xp_nonnegative"),
        sa.CheckConstraint("xp_penalty_applied >= 0", name="consequence_entry_applied_nonnegative"),
        sa.CheckConstraint("xp_penalty_applied <= xp_penalty_requested", name="consequence_entry_applied_lte_requested"),
    )
    op.create_index("ix_consequence_entries_member_id", "consequence_entries", ["member_id"])
    op.create_index("ix_consequence_entries_effective_date", "consequence_entries", ["effective_date"])


def downgrade() -> None:
    op.drop_index("ix_consequence_entries_effective_date", table_name="consequence_entries")
    op.drop_index("ix_consequence_entries_member_id", table_name="consequence_entries")
    op.drop_table("consequence_entries")
    op.drop_table("consequence_presets")
