"""Optional per-child unconditional weekly allowance configuration.

Revision ID: a10c20261014
Revises: f1a20261013b
"""
from alembic import op
import sqlalchemy as sa

revision = "a10c20261014"
down_revision = "f1a20261013b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("family_members", sa.Column("weekly_allowance_cents", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "member_weekly_allowance_positive",
        "family_members",
        "weekly_allowance_cents IS NULL OR (weekly_allowance_cents BETWEEN 1 AND 100000)",
    )

    # Read-only external balances: no credentials, transfers or account numbers.
    op.create_table(
        "member_bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(60), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_member_bank_accounts_member_id", "member_bank_accounts", ["member_id"])
    op.create_table(
        "bank_balance_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("member_bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "observed_at", name="uq_bank_balance_account_observed"),
    )
    op.create_index("ix_bank_balance_snapshots_account_id", "bank_balance_snapshots", ["account_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("member_bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("value_on", sa.Date(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("counterparty", sa.String(200), nullable=True),
        sa.Column("balance_after_cents", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "external_id", name="uq_bank_transaction_external"),
    )
    op.create_index("ix_bank_transactions_account_date", "bank_transactions", ["account_id", "booked_on"])

    op.create_table(
        "money_payment_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_transaction_id", sa.Integer(), sa.ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("category IN ('allowance', 'bonus')", name="payment_match_category"),
        sa.CheckConstraint("amount_cents > 0", name="payment_match_positive"),
        sa.UniqueConstraint("member_id", "category", "week_start", name="uq_payment_match_week_category"),
    )


def downgrade() -> None:
    op.drop_table("money_payment_matches")
    op.drop_table("bank_transactions")
    op.drop_table("bank_balance_snapshots")
    op.drop_table("member_bank_accounts")
    op.drop_constraint("member_weekly_allowance_positive", "family_members", type_="check")
    op.drop_column("family_members", "weekly_allowance_cents")
