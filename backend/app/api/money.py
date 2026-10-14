"""Parent-only money overview and explicit weekly allowance credits.

Balances are shown separately so quest bonus reversals never masquerade as
changes to unconditional pocket money. No payment is initiated here.
"""
import datetime as dt

from fastapi import APIRouter, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.members import get_member
from app.auth import DbSession, ParentSession
from app.demo_mode import NotInDemo
from app.errors import ApiError
from app.models import BankBalanceSnapshot, MemberBankAccount
from app.money import allowance_balance, bonus_balance, money_balance, post_weekly_allowance, weekly_allowance_booked

router = APIRouter(tags=["money"])


class MoneyOverview(BaseModel):
    member_id: int
    allowance_cents: int
    bonus_cents: int
    total_cents: int


@router.get("/members/{member_id}/money", response_model=MoneyOverview)
def get_money_overview(member_id: int, _: ParentSession, db: DbSession) -> MoneyOverview:
    """Parent-only overview; no allowance schedule or bank integration."""
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.child_required")
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


@router.post(
    "/members/{member_id}/money/weekly-allowance",
    response_model=WeeklyAllowanceOut,
    dependencies=[NotInDemo],
)
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


class WeeklyAllowanceStatus(BaseModel):
    member_id: int
    week_start: dt.date
    booked: bool


@router.get("/members/{member_id}/money/weekly-allowance", response_model=WeeklyAllowanceStatus)
def get_weekly_allowance_status(
    member_id: int, week_start: dt.date, _: ParentSession, db: DbSession
) -> WeeklyAllowanceStatus:
    """Check a specific Monday before manually booking pocket money."""
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.child_required")
    try:
        booked = weekly_allowance_booked(db, member_id, week_start)
    except ValueError as exc:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.invalid_allowance") from exc
    return WeeklyAllowanceStatus(member_id=member_id, week_start=week_start, booked=booked)


class WeeklyAllowanceSettings(BaseModel):
    member_id: int
    weekly_amount_cents: int | None


class WeeklyAllowanceSettingsIn(BaseModel):
    weekly_amount_cents: int | None = Field(default=None, ge=1, le=100_000)


@router.get("/members/{member_id}/money/settings", response_model=WeeklyAllowanceSettings)
def get_weekly_allowance_settings(
    member_id: int, _: ParentSession, db: DbSession
) -> WeeklyAllowanceSettings:
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.child_required")
    return WeeklyAllowanceSettings(member_id=member_id, weekly_amount_cents=member.weekly_allowance_cents)


@router.put(
    "/members/{member_id}/money/settings",
    response_model=WeeklyAllowanceSettings,
    dependencies=[NotInDemo],
)
def set_weekly_allowance_settings(
    member_id: int, body: WeeklyAllowanceSettingsIn, _: ParentSession, db: DbSession
) -> WeeklyAllowanceSettings:
    """Opt-in weekly amount; null disables future automatic credits."""
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.child_required")
    member.weekly_allowance_cents = body.weekly_amount_cents
    db.commit()
    return WeeklyAllowanceSettings(member_id=member_id, weekly_amount_cents=member.weekly_allowance_cents)


class BankBalanceOut(BaseModel):
    account_id: int
    display_name: str
    provider: str
    currency: str
    balance_cents: int | None
    observed_at: dt.datetime | None


@router.get("/members/{member_id}/money/bank-balances", response_model=list[BankBalanceOut])
def get_member_bank_balances(
    member_id: int, _: ParentSession, db: DbSession
) -> list[BankBalanceOut]:
    """Read-only latest known bank balances, never calculated from quest credits."""
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "money.child_required")
    accounts = db.scalars(
        select(MemberBankAccount).where(
            MemberBankAccount.member_id == member_id,
            MemberBankAccount.active.is_(True),
        ).order_by(MemberBankAccount.id)
    ).all()
    result = []
    for account in accounts:
        snapshot = db.scalar(
            select(BankBalanceSnapshot)
            .where(BankBalanceSnapshot.account_id == account.id)
            .order_by(BankBalanceSnapshot.observed_at.desc(), BankBalanceSnapshot.id.desc())
            .limit(1)
        )
        result.append(BankBalanceOut(
            account_id=account.id,
            display_name=account.display_name,
            provider=account.provider,
            currency=account.currency,
            balance_cents=snapshot.balance_cents if snapshot else None,
            observed_at=snapshot.observed_at if snapshot else None,
        ))
    return result
