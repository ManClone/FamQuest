"""Introduce optional user family ownership without enabling multiple families.

Existing accounts are assigned to the existing singleton family. The nullable
column intentionally preserves compatibility with legacy fixtures and keeps the
single-family guard in place until authorization is tenant-aware.
"""

import sqlalchemy as sa
from alembic import op

revision = "k20261028userfamily"
down_revision = "j20261016dragon"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("family_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_family_id_families"),
        "users",
        "families",
        ["family_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_users_family_id"), "users", ["family_id"], unique=False)
    op.execute(
        "UPDATE users SET family_id = (SELECT id FROM families LIMIT 1) "
        "WHERE family_id IS NULL AND EXISTS (SELECT 1 FROM families)"
    )


def downgrade():
    op.drop_index(op.f("ix_users_family_id"), table_name="users")
    op.drop_constraint(op.f("fk_users_family_id_families"), "users", type_="foreignkey")
    op.drop_column("users", "family_id")
