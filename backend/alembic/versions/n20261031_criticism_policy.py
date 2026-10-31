"""Fixed criticism level audit and immutable confirmed weekly statements."""

import sqlalchemy as sa
from alembic import op

revision = "n20261031criticism"
down_revision = "m20261031mcpactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consequence_entries", sa.Column("severity", sa.String(20)))
    op.add_column("consequence_entries", sa.Column("request_key", sa.String(32)))
    op.add_column("consequence_entries", sa.Column("star_transaction_id", sa.Integer()))
    op.create_foreign_key(
        "fk_consequence_star_transaction",
        "consequence_entries",
        "point_transactions",
        ["star_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_criticism_actor_request", "consequence_entries", ["created_by_user_id", "request_key"]
    )
    op.create_check_constraint(
        "criticism_fixed_levels",
        "consequence_entries",
        "severity IS NULL OR "
        "(severity = 'conversation' AND xp_penalty_requested = 0 AND money_penalty_cents = 0) OR "
        "(severity = 'light' AND xp_penalty_requested = 1 AND money_penalty_cents = 0) OR "
        "(severity = 'heavy' AND xp_penalty_requested = 2 AND money_penalty_cents IN (0,50)) OR "
        "(severity = 'severe' AND xp_penalty_requested = 3 AND money_penalty_cents IN (0,100))",
    )
    op.create_table(
        "bonus_week_closes",
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("family_members.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("week_start", sa.Date(), primary_key=True),
        sa.Column("allowance_cents", sa.Integer(), nullable=False),
        sa.Column("earned_bonus_cents", sa.Integer(), nullable=False),
        sa.Column("penalty_cents", sa.Integer(), nullable=False),
        sa.Column("payable_bonus_cents", sa.Integer(), nullable=False),
        sa.Column(
            "confirmed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "allowance_cents >= 0 AND earned_bonus_cents >= 0 AND penalty_cents >= 0 "
            "AND payable_bonus_cents >= 0",
            name="closed_week_nonnegative",
        ),
    )


def downgrade() -> None:
    op.drop_table("bonus_week_closes")
    op.drop_constraint("criticism_fixed_levels", "consequence_entries", type_="check")
    op.drop_constraint("uq_criticism_actor_request", "consequence_entries", type_="unique")
    op.drop_constraint("fk_consequence_star_transaction", "consequence_entries", type_="foreignkey")
    op.drop_column("consequence_entries", "star_transaction_id")
    op.drop_column("consequence_entries", "request_key")
    op.drop_column("consequence_entries", "severity")
