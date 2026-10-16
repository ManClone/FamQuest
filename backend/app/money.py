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


def weekly_allowance_booked(db: Session, member_id: int, week_start) -> bool:
    """Read-only check for an existing weekly allowance credit."""
    import datetime as dt

    if (
        not isinstance(week_start, dt.date)
        or isinstance(week_start, dt.datetime)
        or week_start.weekday() != 0
    ):
        raise ValueError("week_start must be a Monday date")
    return (
        db.scalar(
            select(MoneyTransaction.id).where(
                MoneyTransaction.member_id == member_id,
                MoneyTransaction.kind == "allowance",
                MoneyTransaction.reason == f"weekly:{week_start.isoformat()}",
            )
        )
        is not None
    )


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

    member = db.scalar(select(FamilyMember).where(FamilyMember.id == member_id).with_for_update())
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

    if (
        not isinstance(week_start, dt.date)
        or isinstance(week_start, dt.datetime)
        or week_start.weekday() != 0
    ):
        raise ValueError("week_start must be a Monday date")
    if any(
        type(member_id) is not int or type(cents) is not int or not 1 <= cents <= 100_000
        for member_id, cents in configured_amounts.items()
    ):
        raise ValueError("Invalid allowance configuration")

    credited: list[int] = []
    for member_id, cents in sorted(configured_amounts.items()):
        if post_weekly_allowance(db, member_id, cents, week_start):
            credited.append(member_id)
    return credited


def credit_configured_allowances(db: Session, today) -> list[int]:
    """Book this week's configured unconditional allowances, once per child.

    No catch-up for earlier weeks and no payment transfer. Caller commits.
    The member row lock in post_weekly_allowance serializes concurrent runs.
    """
    import datetime as dt

    from app.models import FamilyMember

    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise ValueError("today must be a date")
    monday = today - dt.timedelta(days=today.weekday())
    configured = dict(
        db.execute(
            select(FamilyMember.id, FamilyMember.weekly_allowance_cents).where(
                FamilyMember.role == "child", FamilyMember.weekly_allowance_cents.is_not(None)
            )
        ).all()
    )
    return due_weekly_allowances(db, configured, monday)


def run_weekly_allowance_check() -> list[int]:
    """One transactional check; safe for concurrent app workers and restarts."""
    import datetime as dt
    from zoneinfo import ZoneInfo

    from app.db import engine
    from app.models import Family

    with Session(engine) as db:
        family = db.scalar(select(Family))
        if family is None:
            return []
        today = dt.datetime.now(ZoneInfo(family.timezone or "Europe/Berlin")).date()
        credited = credit_configured_allowances(db, today)
        db.commit()
        return credited


async def run_weekly_allowance_scheduler() -> None:
    """Check once per hour; ledger keys and row locks prevent double booking."""
    import asyncio

    from app.logs import logger

    while True:
        try:
            credited = await asyncio.to_thread(run_weekly_allowance_check)
            if credited:
                logger.info("Wöchentliches Taschengeld gebucht für %s Kinder", len(credited))
        except Exception:
            logger.exception("Taschengeld-Wochenbuchung fehlgeschlagen")
        await asyncio.sleep(3600)


def bonus_payment_reference(week_start) -> str:
    """Stable transfer reference for one ISO calendar week."""
    import datetime as dt

    if (
        not isinstance(week_start, dt.date)
        or isinstance(week_start, dt.datetime)
        or week_start.weekday() != 0
    ):
        raise ValueError("week_start must be a Monday date")
    year, week, _ = week_start.isocalendar()
    return f"Bonus-{year}-W{week:02d}"


def allowance_payment_candidates(
    db: Session,
    member_id: int,
    booked_on,
    amount_cents: int,
    reference: str,
    expected_reference: str = "Taschengeld",
    tolerance_days: int = 5,
):
    """Candidate weeks for a standing-order receipt; never guess across ambiguous weeks.

    This read-only helper does not create matches. The caller must verify the
    account belongs to the child and enforce unique bank transaction assignment.
    """
    import datetime as dt

    from app.models import MoneyPaymentMatch

    if not isinstance(booked_on, dt.date) or isinstance(booked_on, dt.datetime):
        raise ValueError("booked_on must be a date")
    if amount_cents <= 0 or not expected_reference.strip():
        return []
    # Bank descriptions can include prefixes or surrounding whitespace.
    # Only accept the complete reference as a separate phrase.
    import re

    if not re.search(
        r"(?<![\w-])" + re.escape(expected_reference.strip()) + r"(?![\w-])",
        reference,
        re.IGNORECASE,
    ):
        return []
    if not 0 <= tolerance_days <= 7:
        raise ValueError("Invalid tolerance")
    monday = booked_on - dt.timedelta(days=booked_on.weekday())
    weeks = [monday + dt.timedelta(weeks=offset) for offset in (-1, 0, 1)]
    candidates = []
    for week in weeks:
        if abs((booked_on - week).days) > tolerance_days:
            continue
        ledger = db.scalar(
            select(MoneyTransaction).where(
                MoneyTransaction.member_id == member_id,
                MoneyTransaction.kind == "allowance",
                MoneyTransaction.reason == f"weekly:{week.isoformat()}",
            )
        )
        paid_cents = int(
            db.scalar(
                select(func.coalesce(func.sum(MoneyPaymentMatch.amount_cents), 0)).where(
                    MoneyPaymentMatch.member_id == member_id,
                    MoneyPaymentMatch.category == "allowance",
                    MoneyPaymentMatch.week_start == week,
                )
            )
            or 0
        )
        if ledger is not None and 0 < amount_cents <= ledger.amount_cents - paid_cents:
            candidates.append(week)
    return candidates
