"""Read-only money overview for parents.

Balances are shown separately so quest bonus reversals never masquerade as
changes to unconditional pocket money. No payment is initiated here.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.members import get_member
from app.auth import DbSession, ParentSession
from app.money import allowance_balance, bonus_balance, money_balance

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
