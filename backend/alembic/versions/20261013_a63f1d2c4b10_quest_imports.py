"""Quest import idempotency table.

Revision ID: a63f1d2c4b10
Revises: c3a9e51d7b42
"""

import sqlalchemy as sa
from alembic import op

revision = "a63f1d2c4b10"
down_revision = "c3a9e51d7b42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quest_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(120), nullable=False, unique=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
    )


def downgrade():
    op.drop_table("quest_imports")
