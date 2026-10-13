"""Separate monetary ledger: euro cents, never reward points.

A quest bonus is not unconditional pocket money. Callers must use distinct
transaction kinds so allowance cannot be reduced by a bonus reversal.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MoneyTransaction

BONUS_KINDS = frozenset({"task_completed", "task_undone"})
ALLOWANCE_KINDS = frozenset({"allowance"})
PAYMENT_KINDS = frozenset({"payout"})


def book_money(
    db: Session,
    member_id: int,
    cents: int,
    kind: str,
    reason: str,
    completion_id: int | None = None,
) -> None:
    if cents == 0:
        return
    db.add(
        MoneyTransaction(
            member_id=member_id,
            amount_cents=cents,
            kind=kind,
            reason=reason,
            completion_id=completion_id,
        )
    )


def money_balance(db: Session, member_id: int, kinds: frozenset[str] | None = None) -> int:
    """Sum ledger entries, optionally restricted to an explicit money category.

    A bonus reversal can make the bonus subtotal negative; it must not silently
    consume the independently tracked allowance subtotal.
    """
    query = select(func.coalesce(func.sum(MoneyTransaction.amount_cents), 0)).where(
        MoneyTransaction.member_id == member_id
    )
    if kinds is not None:
        query = query.where(MoneyTransaction.kind.in_(kinds))
    return int(db.scalar(query) or 0)


def bonus_balance(db: Session, member_id: int) -> int:
    return money_balance(db, member_id, BONUS_KINDS)


def allowance_balance(db: Session, member_id: int) -> int:
    return money_balance(db, member_id, ALLOWANCE_KINDS)
