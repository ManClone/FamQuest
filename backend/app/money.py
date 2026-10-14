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


def post_weekly_allowance(
    db: Session,
    member_id: int,
    cents: int,
    week_start,
) -> bool:
    """Book an unconditional weekly allowance once per child and ISO week.

    Caller owns the transaction and must commit it. A row lock on the member
    serializes concurrent requests. The allowance does not inspect quest status.
    No scheduling or automatic payments are enabled by this helper.
    """
    import datetime as dt

    from app.models import FamilyMember

    if type(cents) is not int or not 1 <= cents <= 100_000:
        raise ValueError("Allowance must be 1 to 100000 cents")
    if not isinstance(week_start, dt.date) or isinstance(week_start, dt.datetime):
        raise ValueError("week_start must be a date")
    if week_start.weekday() != 0:
        raise ValueError("week_start must be Monday")

    member = db.scalar(
        select(FamilyMember)
        .where(FamilyMember.id == member_id)
        .with_for_update()
    )
    if member is None or member.role != "child":
        raise ValueError("Allowance recipient must be a child")

    key = f"weekly:{week_start.isoformat()}"
    existing = db.scalar(
        select(MoneyTransaction.id).where(
            MoneyTransaction.member_id == member_id,
            MoneyTransaction.kind == "allowance",
            MoneyTransaction.reason == key,
        )
    )
    if existing is not None:
        return False

    book_money(db, member_id, cents, "allowance", key)
    db.flush()
    return True


def due_weekly_allowances(
    db: Session,
    configured_amounts: dict[int, int],
    week_start,
) -> list[int]:
    """Credit configured children for a Monday, safely on repeated runs.

    The caller must supply explicitly configured amounts and commit the
    transaction. This is not a scheduler; it never invents an amount or
    changes the unconditional nature of the allowance.
    Returns IDs of children newly credited in this transaction.
    """
    # Validate the whole batch before writing any ledger entry.
    import datetime as dt

    if not isinstance(week_start, dt.date) or isinstance(week_start, dt.datetime) or week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday date")
    if any(type(member_id) is not int or type(cents) is not int or not 1 <= cents <= 100_000 for member_id, cents in configured_amounts.items()):
        raise ValueError("Invalid allowance configuration")

    credited: list[int] = []
    for member_id, cents in sorted(configured_amounts.items()):
        if post_weekly_allowance(db, member_id, cents, week_start):
            credited.append(member_id)
    return credited
