"""Persist the child's one-time dragon name without changing existing progress."""

import sqlalchemy as sa
from alembic import op

revision = "j20261016dragon"
down_revision = "i20261016stablelevels"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("family_members", sa.Column("dragon_name", sa.String(24), nullable=True))
    op.add_column(
        "family_members",
        sa.Column("dragon_named_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "family_members",
        sa.Column("dragon_named_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_family_members_dragon_named_by_user_id_users"),
        "family_members",
        "users",
        ["dragon_named_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        op.f("fk_family_members_dragon_named_by_user_id_users"),
        "family_members",
        type_="foreignkey",
    )
    op.drop_column("family_members", "dragon_named_by_user_id")
    op.drop_column("family_members", "dragon_named_at")
    op.drop_column("family_members", "dragon_name")
