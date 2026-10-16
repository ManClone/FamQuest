"""Retain an audit trail when parents revoke praise."""

import sqlalchemy as sa
from alembic import op

revision = "g20261016praiserevoke"
down_revision = "f20261016praise"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("praises", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.add_column("praises", sa.Column("revoked_by_user_id", sa.Integer()))
    op.add_column("praises", sa.Column("revocation_reason", sa.String(200)))
    op.create_foreign_key(
        "fk_praises_revoked_by_user_id_users",
        "praises",
        "users",
        ["revoked_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_praises_revoked_by_user_id_users", "praises", type_="foreignkey")
    op.drop_column("praises", "revocation_reason")
    op.drop_column("praises", "revoked_by_user_id")
    op.drop_column("praises", "revoked_at")
