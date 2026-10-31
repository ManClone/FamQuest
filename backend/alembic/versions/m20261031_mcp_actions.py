"""Store family-local MCP action outcomes for safe retries."""

import sqlalchemy as sa
from alembic import op

revision = "m20261031mcpactions"
down_revision = "l20261031choreminutes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_actions",
        sa.Column("identity_id", sa.Integer(), primary_key=True),
        sa.Column("request_key", sa.String(128), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status_code", sa.SmallInteger()),
        sa.Column("response_body", sa.LargeBinary()),
        sa.Column("content_type", sa.String(128)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("mcp_actions")
