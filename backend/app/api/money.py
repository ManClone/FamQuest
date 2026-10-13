"""Read-only money overview for parents.

Balances are shown separately so quest bonus reversals never masquerade as
changes to unconditional pocket money. No payment is initiated here.
"""
import datetime as dt

from fastapi import APIRouter, status
from pydantic import Field
from pydantic import BaseModel

from app.api.members import get_member
from app.auth import DbSession, ParentSession
from app.money import allowance_balance, bonus_balance, money_balance, post_weekly_allowance

router = APIRouter(tags=["money"])


class MoneyOverview(BaseModel):
    member_id: int
    allowance_cents: int
    bonus_cents: int
    total_cents: int


@router.get("/members/{member_id}/money", response_model=MoneyOverview)
def get_money_overview(member_id: int, _: ParentSession, db: DbSession) -> MoneyOverview:
    """Parent-only overview; no allowance schedule or bank integration."""
    get_member(db, member_id)
    return MoneyOverview(
        member_id=member_id,
        allowance_cents=allowance_balance(db, member_id),
        bonus_cents=bonus_balance(db, member_id),
        total_cents=money_balance(db, member_id),
    )


class WeeklyAllowanceIn(BaseModel):
    amount_cents: int = Field(ge=1, le=100_000)
    week_start: dt.date


class WeeklyAllowanceOut(BaseModel):
    member_id: int
    week_start: dt.date
    booked: bool
    allowance_cents: int


@router.post("/members/{member_id}/money/weekly-allowance", response_model=WeeklyAllowanceOut)
def credit_weekly_allowance(
    member_id: int,
    body: WeeklyAllowanceIn,
    _: ParentSession,
    db: DbSession,
) -> WeeklyAllowanceOut:
    """Explicit parent-authorized credit, not a recurring job or bank transfer.

    Idempotent for the child and week. The amount is provided by the parent;
    there is no default amount and no dependency on quest completion.
    """
    from app.errors import ApiError

    try:
        booked = post_weekly_allowance(db, member_id, body.amount_cents, body.week_start)
    except ValueError as exc:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "money.invalid_allowance") from exc
    db.commit()
    return WeeklyAllowanceOut(
        member_id=member_id,
        week_start=body.week_start,
        booked=booked,
        allowance_cents=allowance_balance(db, member_id),
    )
