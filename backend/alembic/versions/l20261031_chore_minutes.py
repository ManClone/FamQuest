"""Snapshot estimated duration for each household execution.

Historical executions deliberately remain NULL; reports label their fallback
to today's chore estimate. No completions, XP or money entries are modified.
"""

import sqlalchemy as sa
from alembic import op

revision = "l20261031choreminutes"
down_revision = "k20261028userfamily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chore_completions", sa.Column("estimated_minutes", sa.SmallInteger()))


def downgrade() -> None:
    op.drop_column("chore_completions", "estimated_minutes")
