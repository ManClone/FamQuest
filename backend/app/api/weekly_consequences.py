"""Parent-only preview of weekly bonus arithmetic (no database writes)."""

import datetime as dt

from fastapi import APIRouter
from sqlalchemy import select
from app.demo_mode import NotInDemo
from app.models import ConsequenceEntry
from app.points import balance, book, lock_member
from app.auth import utcnow
from pydantic import BaseModel, Field

from app.api.members import get_member
from app.auth import DbSession, ParentSession
from app.errors import ApiError
from app.weekly_consequences import weekly_statement, xp_penalty

router = APIRouter(tags=["weekly-consequences"])


class WeeklyPreviewIn(BaseModel):
    member_id: int
    date: dt.date
    earned_bonus_cents: int = Field(ge=0, le=100000)
    money_penalty_cents: int = Field(ge=0, le=100000)


class WeeklyPreviewOut(BaseModel):
    member_id: int
    week_start: dt.date
    week_end: dt.date
    earned_bonus_cents: int
    money_penalty_cents: int
    payable_bonus_cents: int


@router.post("/weekly-consequences/preview", response_model=WeeklyPreviewOut)
def preview_weekly_consequences(
    body: WeeklyPreviewIn, _: ParentSession, db: DbSession
) -> WeeklyPreviewOut:
    """Simulate a week's euro bonus payout without changing XP or allowance."""
    member = get_member(db, body.member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    result = weekly_statement(body.date, body.earned_bonus_cents, body.money_penalty_cents)
    return WeeklyPreviewOut(member_id=member.id, **result.__dict__)


class ConsequenceIn(BaseModel):
    member_id: int
    title: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)
    effective_date: dt.date
    money_penalty_cents: int = Field(ge=0, le=100000)
    xp_penalty: int = Field(ge=0, le=100000)


class ConsequenceOut(BaseModel):
    id: int
    member_id: int
    title: str
    note: str | None
    effective_date: dt.date
    money_penalty_cents: int
    xp_penalty_requested: int
    xp_penalty_applied: int
    reversed: bool


def consequence_out(entry: ConsequenceEntry) -> ConsequenceOut:
    return ConsequenceOut(
        id=entry.id,
        member_id=entry.member_id,
        title=entry.title,
        note=entry.note,
        effective_date=entry.effective_date,
        money_penalty_cents=entry.money_penalty_cents,
        xp_penalty_requested=entry.xp_penalty_requested,
        xp_penalty_applied=entry.xp_penalty_applied,
        reversed=entry.reversed_at is not None,
    )


@router.get("/members/{member_id}/consequences", response_model=list[ConsequenceOut])
def list_consequences(member_id: int, _: ParentSession, db: DbSession) -> list[ConsequenceOut]:
    get_member(db, member_id)
    entries = db.scalars(
        select(ConsequenceEntry)
        .where(ConsequenceEntry.member_id == member_id)
        .order_by(ConsequenceEntry.id.desc())
    ).all()
    return [consequence_out(entry) for entry in entries]


@router.post("/consequences", response_model=ConsequenceOut, status_code=201, dependencies=[NotInDemo])
def create_consequence(body: ConsequenceIn, auth_session: ParentSession, db: DbSession) -> ConsequenceOut:
    member = get_member(db, body.member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    lock_member(db, member.id)
    deduction = xp_penalty(balance(db, member.id), body.xp_penalty)
    entry = ConsequenceEntry(
        member_id=member.id,
        title=body.title,
        note=body.note,
        effective_date=body.effective_date,
        money_penalty_cents=body.money_penalty_cents,
        xp_penalty_requested=body.xp_penalty,
        xp_penalty_applied=deduction.deducted_xp,
        created_by_user_id=auth_session.user_id,
    )
    db.add(entry)
    if deduction.deducted_xp:
        book(db, member.id, -deduction.deducted_xp, "consequence", reason=body.title, user_id=auth_session.user_id)
    db.commit()
    db.refresh(entry)
    return consequence_out(entry)


@router.post("/consequences/{entry_id}/reverse", response_model=ConsequenceOut, dependencies=[NotInDemo])
def reverse_consequence(entry_id: int, auth_session: ParentSession, db: DbSession) -> ConsequenceOut:
    entry = db.get(ConsequenceEntry, entry_id)
    if entry is None:
        raise ApiError(404, "common.not_found")
    lock_member(db, entry.member_id)
    db.refresh(entry)
    if entry.reversed_at is not None:
        return consequence_out(entry)
    if entry.xp_penalty_applied:
        book(db, entry.member_id, entry.xp_penalty_applied, "consequence_reversed", reason=entry.title, user_id=auth_session.user_id)
    entry.reversed_at = utcnow()
    entry.reversed_by_user_id = auth_session.user_id
    db.commit()
    db.refresh(entry)
    return consequence_out(entry)
