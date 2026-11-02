"""Parent-only consequence ledger and weekly bonus preview."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.members import get_member
from app.auth import DbSession, ParentSession, get_family, utcnow
from app.criticism_policy import LEVELS, amounts
from app.demo_mode import NotInDemo
from app.errors import ApiError
from app.models import (
    BonusWeekClose,
    ChoreCompletion,
    ConsequenceEntry,
    MoneyPaymentMatch,
    MoneyTransaction,
    TaskCompletion,
)
from app.points import balance, book, lock_member
from app.today import family_now
from app.weekly_consequences import monday_of, weekly_statement, xp_penalty

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
    model_config = {"extra": "forbid"}
    member_id: int
    title: str = Field(min_length=1, max_length=100, pattern=r"\S")
    note: str | None = Field(default=None, max_length=500)
    effective_date: dt.date | None = None
    severity: Literal["conversation", "light", "heavy", "severe"]
    apply_money: bool = False
    confirmed: Literal[True]
    request_key: str = Field(pattern=r"^[a-f0-9]{32}$")
    expected_bonus_cents: int | None = Field(default=None, ge=0)


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
    severity: str | None = None
    reversal_note: str | None = None


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
        severity=entry.severity,
        reversal_note=entry.reversal_note,
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


@router.post(
    "/consequences", response_model=ConsequenceOut, status_code=201, dependencies=[NotInDemo]
)
def create_consequence(
    body: ConsequenceIn, auth_session: ParentSession, db: DbSession
) -> ConsequenceOut:
    member = get_member(db, body.member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    lock_member(db, member.id)
    today = family_now(get_family(db)).date()
    effective = body.effective_date or today
    previous = db.scalar(
        select(ConsequenceEntry).where(
            ConsequenceEntry.created_by_user_id == auth_session.user_id,
            ConsequenceEntry.request_key == body.request_key,
        )
    )
    if previous is not None:
        if (
            previous.member_id != body.member_id
            or previous.title != body.title.strip()
            or previous.note != body.note
            or previous.severity != body.severity
            or previous.effective_date != effective
            or bool(previous.money_penalty_cents) != body.apply_money
        ):
            raise ApiError(409, "criticism.request_conflict")
        return consequence_out(previous)
    if not monday_of(today) <= effective <= today:
        raise ApiError(422, "criticism.current_week_required")
    state = week_state(db, member.id, effective)
    if body.apply_money and body.expected_bonus_cents != state["payable_bonus_cents"]:
        raise ApiError(409, "criticism.statement_changed")
    try:
        stars, money = amounts(
            body.severity,
            apply_money=body.apply_money,
            available_bonus=state["payable_bonus_cents"],
            closed=state["closed"],
        )
    except ValueError:
        raise ApiError(409, "criticism.bonus_protected") from None
    deduction = xp_penalty(balance(db, member.id), stars)
    entry = ConsequenceEntry(
        member_id=member.id,
        title=body.title.strip(),
        note=body.note,
        effective_date=effective,
        severity=body.severity,
        request_key=body.request_key,
        money_penalty_cents=money,
        xp_penalty_requested=stars,
        xp_penalty_applied=deduction.deducted_xp,
        created_by_user_id=auth_session.user_id,
    )
    db.add(entry)
    if deduction.deducted_xp:
        transaction = book(
            db,
            member.id,
            -deduction.deducted_xp,
            "consequence",
            reason=body.title,
            user_id=auth_session.user_id,
        )
        db.flush()
        entry.star_transaction_id = transaction.id
    db.commit()
    db.refresh(entry)
    return consequence_out(entry)


class ReversalIn(BaseModel):
    confirmed: Literal[True]
    reason: str = Field(min_length=1, max_length=500, pattern=r"\S")


@router.post(
    "/consequences/{entry_id}/reverse", response_model=ConsequenceOut, dependencies=[NotInDemo]
)
def reverse_consequence(
    entry_id: int, body: ReversalIn, auth_session: ParentSession, db: DbSession
) -> ConsequenceOut:
    entry = db.get(ConsequenceEntry, entry_id)
    if entry is None:
        raise ApiError(404, "common.not_found")
    lock_member(db, entry.member_id)
    db.refresh(entry)
    if entry.reversed_at is not None:
        return consequence_out(entry)
    if (
        entry.money_penalty_cents
        and week_state(db, entry.member_id, entry.effective_date)["closed"]
    ):
        raise ApiError(409, "criticism.week_closed")
    if entry.xp_penalty_applied:
        book(
            db,
            entry.member_id,
            entry.xp_penalty_applied,
            "consequence_reversed",
            reason=entry.title,
            user_id=auth_session.user_id,
        )
    entry.reversed_at = utcnow()
    entry.reversed_by_user_id = auth_session.user_id
    entry.reversal_note = body.reason.strip()
    db.commit()
    db.refresh(entry)
    return consequence_out(entry)


@router.get("/members/{member_id}/weekly-bonus", response_model=WeeklyPreviewOut)
def actual_weekly_bonus(
    member_id: int, date: dt.date, _: ParentSession, db: DbSession
) -> WeeklyPreviewOut:
    """Read actual task bonus and active penalties for one family-local ISO week."""
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    state = week_state(db, member_id, date)
    return WeeklyPreviewOut(**{key: state[key] for key in WeeklyPreviewOut.model_fields})


def raw_week(db, member_id, date):
    start = monday_of(date)
    end = start + dt.timedelta(days=6)
    earned = (
        db.scalar(
            select(func.coalesce(func.sum(MoneyTransaction.amount_cents), 0))
            .join(TaskCompletion, MoneyTransaction.completion_id == TaskCompletion.id)
            .where(
                MoneyTransaction.member_id == member_id,
                MoneyTransaction.kind.in_(("task_completed", "task_undone")),
                TaskCompletion.date >= start,
                TaskCompletion.date <= end,
            )
        )
        or 0
    )
    earned += (
        db.scalar(
            select(func.coalesce(func.sum(MoneyTransaction.amount_cents), 0))
            .join(ChoreCompletion, MoneyTransaction.completion_id == ChoreCompletion.id)
            .where(
                MoneyTransaction.member_id == member_id,
                MoneyTransaction.kind.in_(("chore_completed", "chore_undone")),
                ChoreCompletion.date >= start,
                ChoreCompletion.date <= end,
            )
        )
        or 0
    )
    penalties = (
        db.scalar(
            select(func.coalesce(func.sum(ConsequenceEntry.money_penalty_cents), 0)).where(
                ConsequenceEntry.member_id == member_id,
                ConsequenceEntry.effective_date >= start,
                ConsequenceEntry.effective_date <= end,
                ConsequenceEntry.reversed_at.is_(None),
            )
        )
        or 0
    )
    allowance = (
        db.scalar(
            select(func.coalesce(func.sum(MoneyTransaction.amount_cents), 0)).where(
                MoneyTransaction.member_id == member_id,
                MoneyTransaction.kind == "allowance",
                MoneyTransaction.reason == f"weekly:{start.isoformat()}",
            )
        )
        or 0
    )
    return max(0, int(earned)), int(penalties), max(0, int(allowance))


def week_state(db, member_id, date):
    start = monday_of(date)
    earned, penalties, allowance = raw_week(db, member_id, date)
    frozen = db.get(BonusWeekClose, (member_id, start))
    paid = (
        db.scalar(
            select(MoneyPaymentMatch.id)
            .where(
                MoneyPaymentMatch.member_id == member_id,
                MoneyPaymentMatch.week_start == start,
                MoneyPaymentMatch.category == "bonus",
            )
            .limit(1)
        )
        is not None
    )
    changed = False
    if frozen is not None:
        changed = (earned, penalties, allowance) != (
            frozen.earned_bonus_cents,
            frozen.penalty_cents,
            frozen.allowance_cents,
        )
        earned, penalties, allowance = (
            frozen.earned_bonus_cents,
            frozen.penalty_cents,
            frozen.allowance_cents,
        )
    result = weekly_statement(date, earned, penalties)
    return {
        "member_id": member_id,
        **result.__dict__,
        "allowance_cents": allowance,
        "total_cents": allowance + result.payable_bonus_cents,
        "closed": frozen is not None or paid,
        "recorded_payment": paid,
        "requires_review": changed,
    }


@router.get("/members/{member_id}/criticism")
def criticism_context(member_id: int, _: ParentSession, db: DbSession):
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    today = family_now(get_family(db)).date()
    return {
        **week_state(db, member_id, today),
        "date": today,
        "levels": {
            name: {"stars": level.stars, "bonus_cents": level.bonus_cents}
            for name, level in LEVELS.items()
        },
        "spendable_stars": balance(db, member_id),
    }


class CloseWeekIn(BaseModel):
    model_config = {"extra": "forbid"}
    date: dt.date
    confirmed: Literal[True]
    expected_total_cents: int = Field(ge=0)


@router.post("/members/{member_id}/weekly-bonus/close")
def close_week(member_id: int, body: CloseWeekIn, actor: ParentSession, db: DbSession):
    member = get_member(db, member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    lock_member(db, member_id)
    today = family_now(get_family(db)).date()
    if body.date > today:
        raise ApiError(422, "criticism.current_week_required")
    state = week_state(db, member_id, body.date)
    if state["total_cents"] != body.expected_total_cents:
        raise ApiError(409, "criticism.statement_changed")
    if db.get(BonusWeekClose, (member_id, state["week_start"])) is not None:
        return state
    if state["recorded_payment"]:
        raise ApiError(409, "criticism.week_closed")
    db.add(
        BonusWeekClose(
            member_id=member_id,
            week_start=state["week_start"],
            allowance_cents=state["allowance_cents"],
            earned_bonus_cents=state["earned_bonus_cents"],
            penalty_cents=state["money_penalty_cents"],
            payable_bonus_cents=state["payable_bonus_cents"],
            confirmed_by_user_id=actor.user_id,
        )
    )
    db.commit()
    return week_state(db, member_id, body.date)
