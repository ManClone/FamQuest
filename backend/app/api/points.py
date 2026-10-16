from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.members import get_member
from app.auth import CurrentSession, DbSession, ParentSession, ensure_member_access
from app.errors import ApiError
from app.models import PointTransaction, Praise
from app.points import balance, book, level_xp, lock_member
from app.schemas import PointBookingIn, PointHistoryOut, PointTransactionOut

router = APIRouter(tags=["points"])

HISTORY_PAGE_SIZE = 50


def transaction_out(transaction: PointTransaction) -> PointTransactionOut:
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
    return PointHistoryOut(
        total=balance(db, member_id),
        transactions=[transaction_out(t) for t in transactions[:limit]],
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
    earned = level_xp(db, member_id)
    # Display-only levels: level 1 starts at 0 XP, each next level needs 100 XP.
    step = 100
    latest = db.scalar(
        select(Praise).where(Praise.member_id == member_id).order_by(Praise.id.desc()).limit(1)
    )
    praise_count = db.scalar(
        select(func.count()).select_from(Praise).where(Praise.member_id == member_id)
    )
    return {
        "praise_count": praise_count or 0,
        "latest_praise_id": latest.id if latest else 0,
        "latest_praise_reason": latest.reason if latest else None,
        "earned_xp": earned,
        "level": earned // step + 1,
        "level_progress": earned % step,
        "level_size": step,
        "remaining_xp": step - earned % step,
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
            {"id": item.id, "reason": item.reason, "created_at": item.created_at}
            for item in entries[:50]
        ],
        "has_more": len(entries) > 50,
    }
