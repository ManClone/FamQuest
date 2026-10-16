"""Persist unlocked levels, protecting existing 100-XP legacy levels."""

import sqlalchemy as sa
from alembic import op

revision = "i20261016stablelevels"
down_revision = "h20261016penalty"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "family_members",
        sa.Column("highest_level", sa.Integer(), nullable=False, server_default="1"),
    )
    # Protect the highest historical legacy level, even if tasks were later undone.
    op.execute("""
        WITH running AS (
            SELECT member_id, SUM(amount) OVER (
                PARTITION BY member_id ORDER BY id ROWS UNBOUNDED PRECEDING
            ) AS earned
            FROM point_transactions
            WHERE kind IN ('task_completed','task_undone','chore_completed','chore_undone')
        ), legacy AS (
            SELECT member_id, GREATEST(1, FLOOR(MAX(earned) / 100.0)::integer + 1) AS level
            FROM running GROUP BY member_id
        )
        UPDATE family_members m SET highest_level = legacy.level
        FROM legacy WHERE m.id = legacy.member_id
    """)


def downgrade():
    op.drop_column("family_members", "highest_level")
