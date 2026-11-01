"""Optional household child bonus; existing chores and executions retain zero euros."""

import sqlalchemy as sa
from alembic import op

revision = "q20261101chorebonus"
down_revision = "p20261101reactivate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("chores", "chore_completions"):
        op.add_column(
            table, sa.Column("money_cents", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    op.drop_column("chore_completions", "money_cents")
    op.drop_column("chores", "money_cents")
