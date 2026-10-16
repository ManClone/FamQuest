"""One correction per manual ledger entry, shared by penalty and manual APIs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import PenaltyReversal, PointTransaction
from app.points import balance, book, lock_member


def compensation_candidates(db: Session, entry: PointTransaction) -> list[int]:
    if entry.amount >= 0:
        return []
    return list(
        db.scalars(
            select(PointTransaction.id)
            .where(
                PointTransaction.member_id == entry.member_id,
                PointTransaction.kind == "manual",
                PointTransaction.amount == -entry.amount,
                PointTransaction.id > entry.id,
            )
            .order_by(PointTransaction.id)
        )
    )


def reverse_manual(
    db: Session,
    member_id: int,
    transaction_id: int,
    user_id: int,
    reason: str,
    *,
    penalty_only: bool = False,
    existing_compensation_id: int | None = None,
    compensation_reviewed: bool = False,
) -> PenaltyReversal:
    lock_member(db, member_id)
    entry = db.scalar(
        select(PointTransaction)
        .where(PointTransaction.id == transaction_id, PointTransaction.member_id == member_id)
        .with_for_update(of=PointTransaction)
    )
    if entry is None:
        raise ApiError(404, "common.not_found")
    if entry.kind != "manual" or (penalty_only and entry.amount >= 0):
        raise ApiError(409, "points.not_penalty" if penalty_only else "points.not_manual")
    reversal = db.get(PenaltyReversal, transaction_id)
    if reversal:
        return reversal
    # A previously linked manual compensation cannot itself be refunded a second time.
    if db.scalar(
        select(PenaltyReversal.transaction_id).where(
            PenaltyReversal.refund_transaction_id == transaction_id
        )
    ):
        raise ApiError(409, "points.compensation_in_use")
    if existing_compensation_id is not None:
        refund = db.get(PointTransaction, existing_compensation_id)
        if (
            refund is None
            or refund.member_id != member_id
            or refund.kind != "manual"
            or refund.amount != -entry.amount
            or refund.id <= entry.id
            or db.get(PenaltyReversal, refund.id) is not None
            or db.scalar(
                select(PenaltyReversal.transaction_id).where(
                    PenaltyReversal.refund_transaction_id == refund.id
                )
            )
            is not None
        ):
            raise ApiError(409, "points.invalid_compensation")
    else:
        if compensation_candidates(db, entry) and not compensation_reviewed:
            raise ApiError(409, "points.compensation_review_required")
        if balance(db, member_id) - entry.amount < 0:
            raise ApiError(409, "points.insufficient")
        refund = book(
            db,
            member_id,
            -entry.amount,
            "penalty_reversed" if penalty_only else "manual_reversed",
            reason=reason.strip(),
            user_id=user_id,
        )
        db.flush()
    reversal = PenaltyReversal(
        transaction_id=entry.id,
        refund_transaction_id=refund.id,
        reason=reason.strip(),
        created_by_user_id=user_id,
    )
    db.add(reversal)
    db.flush()
    return reversal
