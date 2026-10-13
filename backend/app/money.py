"""Separate monetary ledger. All values are integer euro cents."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MoneyTransaction


def book_money(db: Session, member_id: int, cents: int, kind: str, reason: str, completion_id: int | None = None) -> None:
    if cents == 0:
        return
    db.add(MoneyTransaction(
        member_id=member_id,
        amount_cents=cents,
        kind=kind,
        reason=reason,
        completion_id=completion_id,
    ))


def money_balance(db: Session, member_id: int) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(MoneyTransaction.amount_cents), 0))
        .where(MoneyTransaction.member_id == member_id)
    ) or 0)
