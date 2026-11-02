"""Keep exact completion origins in the point ledger for a unified activity list."""

import sqlalchemy as sa
from alembic import op

revision = "o20261101links"
down_revision = "n20261031criticism"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("point_transactions", sa.Column("completion_source", sa.String(10)))
    op.add_column("point_transactions", sa.Column("completion_id", sa.Integer()))


def downgrade() -> None:
    op.drop_column("point_transactions", "completion_id")
    op.drop_column("point_transactions", "completion_source")
