"""Map identities to family-local actor references without guessing existing IDs."""

import sqlalchemy as sa
from alembic import op

revision = "e20261031_actors"
down_revision = "d20261031_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("family_user_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("memberships") as batch:
        batch.create_unique_constraint(
            "uq_membership_family_actor", ["tenant_id", "family_user_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("memberships") as batch:
        batch.drop_constraint("uq_membership_family_actor", type_="unique")
        batch.drop_column("family_user_id")
