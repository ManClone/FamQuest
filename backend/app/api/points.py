from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.members import get_member
from app.auth import CurrentSession, DbSession, ParentSession, ensure_member_access
from app.errors import ApiError
from app.levels import progress
from app.models import PenaltyReversal, PointTransaction, Praise
from app.point_reversals import compensation_candidates, reverse_manual
from app.points import balance, book, lock_member
from app.schemas import PointBookingIn, PointHistoryOut, PointTransactionOut
from app.today import utcnow

router = APIRouter(tags=["points"])

HISTORY_PAGE_SIZE = 50


def transaction_out(
    transaction: PointTransaction,
    reversal: PenaltyReversal | None = None,
    compensates: int | None = None,
) -> PointTransactionOut:
    return PointTransactionOut(
        id=transaction.id,
        amount=transaction.amount,
        kind=transaction.kind,
        reason=transaction.reason,
        icon=transaction.redemption.reward_icon
        if transaction.redemption
        else transaction.task.icon
        if transaction.task
        else None,
        task_date=transaction.task_date,
        created_at=transaction.created_at,
        reversed_at=reversal.created_at if reversal else None,
        reversal_transaction_id=reversal.refund_transaction_id if reversal else None,
        reversal_reason=reversal.reason if reversal else None,
        compensates_transaction_id=compensates,
    )


@router.get("/members/{member_id}/points")
def get_points(
    member_id: int,
    auth: CurrentSession,
    db: DbSession,
    before: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=HISTORY_PAGE_SIZE)] = HISTORY_PAGE_SIZE,
) -> PointHistoryOut:
    """Punktestand und Buchungen einer Person, neueste zuerst."""
    ensure_member_access(db, auth, member_id)
    get_member(db, member_id)
    query = select(PointTransaction).where(PointTransaction.member_id == member_id)
    if before is not None:
        query = query.where(PointTransaction.id < before)
    transactions = list(db.scalars(query.order_by(PointTransaction.id.desc()).limit(limit + 1)))
    ids = [t.id for t in transactions[:limit]]
    reversals = {
        r.transaction_id: r
        for r in db.scalars(select(PenaltyReversal).where(PenaltyReversal.transaction_id.in_(ids)))
    }
    compensations = {
        r.refund_transaction_id: r.transaction_id
        for r in db.scalars(
            select(PenaltyReversal).where(PenaltyReversal.refund_transaction_id.in_(ids))
        )
    }
    return PointHistoryOut(
        total=balance(db, member_id),
        transactions=[
            transaction_out(t, reversals.get(t.id), compensations.get(t.id))
            for t in transactions[:limit]
        ],
        has_more=len(transactions) > limit,
    )


@router.post("/members/{member_id}/points", status_code=status.HTTP_201_CREATED)
def add_points(
    member_id: int, body: PointBookingIn, auth_session: ParentSession, db: DbSession
) -> PointHistoryOut:
    """Manuelle Gutschrift oder Abzug; der Punktestand darf dabei nicht negativ werden."""
    get_member(db, member_id)
    lock_member(db, member_id)
    if body.amount < 0 and balance(db, member_id) + body.amount < 0:
        raise ApiError(status.HTTP_409_CONFLICT, "points.insufficient")
    book(db, member_id, body.amount, "manual", reason=body.reason, user_id=auth_session.user_id)
    db.commit()
    return get_points(member_id, auth_session, db)


@router.get("/members/{member_id}/progress")
def member_progress(
    member_id: int, auth: CurrentSession, db: DbSession
) -> dict[str, int | str | None]:
    """Levels use earned task XP, never the balance spent on rewards."""
    ensure_member_access(db, auth, member_id)
    get_member(db, member_id)
    latest = db.scalar(
        select(Praise)
        .where(Praise.member_id == member_id, Praise.revoked_at.is_(None))
        .order_by(Praise.id.desc())
        .limit(1)
    )
    praise_count = db.scalar(
        select(func.count())
        .select_from(Praise)
        .where(Praise.member_id == member_id, Praise.revoked_at.is_(None))
    )
    deduction = db.scalar(
        select(PointTransaction)
        .where(
            PointTransaction.member_id == member_id,
            PointTransaction.kind == "manual",
            PointTransaction.amount < 0,
            ~select(PenaltyReversal.transaction_id)
            .where(PenaltyReversal.transaction_id == PointTransaction.id)
            .exists(),
            ~select(PenaltyReversal.transaction_id)
            .where(PenaltyReversal.refund_transaction_id == PointTransaction.id)
            .exists(),
        )
        .order_by(PointTransaction.id.desc())
        .limit(1)
    )
    return {
        "latest_deduction_id": deduction.id if deduction else 0,
        "latest_deduction_reason": deduction.reason if deduction else None,
        "latest_deduction_amount": -deduction.amount if deduction else 0,
        "praise_count": praise_count or 0,
        "latest_praise_id": latest.id if latest else 0,
        "latest_praise_reason": latest.reason if latest else None,
        **progress(db, member_id),
    }


class PraiseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200, pattern=r"\S")
    request_key: str = Field(min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")


@router.post("/members/{member_id}/praise", status_code=201)
def add_praise(member_id: int, body: PraiseIn, auth: ParentSession, db: DbSession) -> dict:
    from app.praise import grant_praise

    entry = grant_praise(
        db, member_id, auth.user_id, body.reason.strip(), "manual:" + body.request_key
    )
    db.commit()
    return {"id": entry.id, "reason": entry.reason}


@router.get("/members/{member_id}/praise")
def praise_history(
    member_id: int,
    auth: CurrentSession,
    db: DbSession,
    before: int | None = Query(default=None, ge=1),
) -> dict:
    ensure_member_access(db, auth, member_id)
    get_member(db, member_id)
    query = select(Praise).where(Praise.member_id == member_id)
    if before is not None:
        query = query.where(Praise.id < before)
    entries = list(db.scalars(query.order_by(Praise.id.desc()).limit(51)))
    return {
        "praises": [
            {
                "id": item.id,
                "reason": item.reason,
                "created_at": item.created_at,
                "revoked_at": item.revoked_at,
                "revocation_reason": item.revocation_reason,
            }
            for item in entries[:50]
        ],
        "has_more": len(entries) > 50,
    }


class PraiseRevocationIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200, pattern=r"\S")


@router.post("/members/{member_id}/praise/{praise_id}/revoke")
def revoke_praise(
    member_id: int, praise_id: int, body: PraiseRevocationIn, auth: ParentSession, db: DbSession
) -> dict:
    """Revoke one heart once; retain original reason, creator and correction audit."""
    get_member(db, member_id)
    lock_member(db, member_id)
    entry = db.scalar(
        select(Praise)
        .where(Praise.id == praise_id, Praise.member_id == member_id)
        .with_for_update()
    )
    if entry is None:
        raise ApiError(404, "common.not_found")
    if entry.revoked_at is None:
        from app.levels import advance

        advance(db, member_id)
        entry.revoked_at = utcnow()
        entry.revoked_by_user_id = auth.user_id
        entry.revocation_reason = body.reason.strip()
        db.commit()
    return {
        "id": entry.id,
        "revoked_at": entry.revoked_at.astimezone(UTC),
        "revocation_reason": entry.revocation_reason,
    }


@router.get("/members/{member_id}/penalties")
def penalty_history(
    member_id: int, _: ParentSession, db: DbSession, before: int | None = Query(default=None, ge=1)
) -> dict:
    """Original manual deductions with their refund audit, newest first."""
    get_member(db, member_id)
    query = (
        select(PointTransaction, PenaltyReversal)
        .outerjoin(PenaltyReversal, PenaltyReversal.transaction_id == PointTransaction.id)
        .where(
            PointTransaction.member_id == member_id,
            PointTransaction.kind == "manual",
            PointTransaction.amount < 0,
        )
        .order_by(PointTransaction.id.desc())
        .limit(51)
    )
    if before is not None:
        query = query.where(PointTransaction.id < before)
    rows = list(db.execute(query))
    return {
        "penalties": [
            {
                "id": entry.id,
                "amount": -entry.amount,
                "reason": entry.reason,
                "created_at": entry.created_at,
                "reversed_at": reversal.created_at if reversal else None,
                "reversal_reason": reversal.reason if reversal else None,
                "refund_transaction_id": reversal.refund_transaction_id if reversal else None,
                "compensates_transaction_id": db.scalar(
                    select(PenaltyReversal.transaction_id).where(
                        PenaltyReversal.refund_transaction_id == entry.id
                    )
                ),
                "compensation_candidate_ids": compensation_candidates(db, entry)
                if reversal is None
                else [],
            }
            for entry, reversal in rows[:50]
        ],
        "has_more": len(rows) > 50,
    }


class PointReversalIn(PraiseRevocationIn):
    existing_compensation_id: int | None = Field(default=None, ge=1)
    compensation_reviewed: bool = False


def reverse_points_entry(member_id, transaction_id, body, auth, db, *, penalty_only=False):
    get_member(db, member_id)
    reversal = reverse_manual(
        db,
        member_id,
        transaction_id,
        auth.user_id,
        body.reason,
        penalty_only=penalty_only,
        existing_compensation_id=body.existing_compensation_id,
        compensation_reviewed=body.compensation_reviewed,
    )
    db.commit()
    return {
        "transaction_id": reversal.transaction_id,
        "refund_transaction_id": reversal.refund_transaction_id,
        "amount": -db.get(PointTransaction, transaction_id).amount,
        "reversed_at": reversal.created_at,
        "reason": reversal.reason,
    }


@router.post("/members/{member_id}/penalties/{transaction_id}/reverse")
def reverse_penalty(
    member_id: int,
    transaction_id: int,
    body: PointReversalIn,
    auth: ParentSession,
    db: DbSession,
) -> dict:
    """Reverse a manual deduction once; review/link existing compensation before refunding."""
    return reverse_points_entry(member_id, transaction_id, body, auth, db, penalty_only=True)


@router.post("/members/{member_id}/points/{transaction_id}/reverse")
def reverse_points(
    member_id: int,
    transaction_id: int,
    body: PointReversalIn,
    auth: ParentSession,
    db: DbSession,
) -> dict:
    """Reverse one manual credit/debit. Never reverses task, reward or refund entries.

    A negative booking uses the same audit as penalty reversal, preventing double refunds.
    Existing compensation must be explicitly linked, or reviewed as unrelated.
    """
    return reverse_points_entry(member_id, transaction_id, body, auth, db)
