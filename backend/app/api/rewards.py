from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.members import get_member
from app.auth import CurrentSession, DbSession, ParentSession, child_member_id, ensure_member_access
from app.errors import ApiError
from app.models import PointTransaction, Reward, RewardRedemption
from app.points import balance, book, lock_member
from app.schemas import CancelRedemptionIn, RedemptionHistoryOut, RedemptionOut, RewardIn, RewardOut

router = APIRouter(tags=["rewards"])

HISTORY_PAGE_SIZE = 50


def reward_out(reward: Reward) -> RewardOut:
    return RewardOut(
        id=reward.id,
        member_id=reward.member_id,
        name=reward.name,
        icon=reward.icon,
        description=reward.description or "",
        cost=reward.cost,
        active=reward.active,
    )


def redemption_out(
    redemption: RewardRedemption, cancellation: PointTransaction | None = None
) -> RedemptionOut:
    return RedemptionOut(
        id=redemption.id,
        reward_id=redemption.reward_id,
        member_id=redemption.member_id,
        status=redemption.status,
        reward_name=redemption.reward_name,
        reward_icon=redemption.reward_icon,
        cost=redemption.cost,
        created_at=redemption.created_at,
        cancellation_reason=cancellation.reason if cancellation else None,
        cancelled_at=cancellation.created_at if cancellation else None,
    )


def get_reward(db: DbSession, reward_id: int) -> Reward:
    reward = db.get(Reward, reward_id)
    if reward is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "reward.not_found")
    return reward


def apply_reward(db: DbSession, reward: Reward, body: RewardIn) -> None:
    get_member(db, body.member_id)
    reward.member_id, reward.name, reward.icon = body.member_id, body.name, body.icon
    reward.description = body.description or None
    reward.cost, reward.active = body.cost, body.active


@router.get("/rewards")
def list_rewards(auth: CurrentSession, db: DbSession) -> list[RewardOut]:
    """Alle Belohnungen; das Display zeigt davon nur die aktiven."""
    rewards = db.scalars(select(Reward).order_by(Reward.member_id, Reward.cost, Reward.id))
    own = child_member_id(db, auth)
    return [reward_out(reward) for reward in rewards if own is None or reward.member_id == own]


@router.post("/rewards", status_code=status.HTTP_201_CREATED)
def create_reward(body: RewardIn, _: ParentSession, db: DbSession) -> RewardOut:
    reward = Reward()
    apply_reward(db, reward, body)
    db.add(reward)
    db.commit()
    return reward_out(reward)


@router.put("/rewards/{reward_id}")
def update_reward(reward_id: int, body: RewardIn, _: ParentSession, db: DbSession) -> RewardOut:
    reward = get_reward(db, reward_id)
    apply_reward(db, reward, body)
    db.commit()
    return reward_out(reward)


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reward(reward_id: int, _: ParentSession, db: DbSession) -> None:
    db.delete(get_reward(db, reward_id))
    db.commit()


@router.post("/rewards/{reward_id}/redeem", status_code=status.HTTP_201_CREATED)
def redeem_reward(reward_id: int, auth: CurrentSession, db: DbSession) -> RedemptionOut:
    """Löst eine Belohnung für ihr Kind ein, am Display ohne Eltern-PIN.

    Punktestand und Kosten werden in derselben Transaktion geprüft; die Sperre auf die Person
    verhindert, dass zwei gleichzeitige Einlösungen den Stand ins Minus bringen.
    """
    reward = get_reward(db, reward_id)
    ensure_member_access(db, auth, reward.member_id)
    member = get_member(db, reward.member_id)
    if not reward.active:
        raise ApiError(status.HTTP_409_CONFLICT, "reward.inactive")
    lock_member(db, member.id)
    if balance(db, member.id) < reward.cost:
        raise ApiError(status.HTTP_409_CONFLICT, "reward.insufficient_points")

    redemption = RewardRedemption(
        reward_id=reward.id,
        member_id=member.id,
        status="redeemed",
        reward_name=reward.name,
        reward_icon=reward.icon,
        cost=reward.cost,
    )
    db.add(redemption)
    db.flush()
    book(db, member.id, -reward.cost, "reward_redeemed", reason=reward.name, redemption=redemption)
    db.commit()
    return redemption_out(redemption)


@router.post("/redemptions/{redemption_id}/cancel")
def cancel_redemption(
    redemption_id: int, body: CancelRedemptionIn, auth: ParentSession, db: DbSession
) -> RedemptionOut:
    redemption = db.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "reward.not_found")
    lock_member(db, redemption.member_id)
    # Re-read after acquiring the member lock: simultaneous requests refund only once.
    db.refresh(redemption)
    if redemption.status != "cancelled":
        book(
            db,
            redemption.member_id,
            redemption.cost,
            "reward_cancelled",
            reason=body.reason,
            user_id=auth.user_id,
            redemption=redemption,
        )
        redemption.status = "cancelled"
        db.commit()
    cancellation = db.scalar(
        select(PointTransaction).where(
            PointTransaction.redemption_id == redemption.id,
            PointTransaction.kind == "reward_cancelled",
        )
    )
    return redemption_out(redemption, cancellation)


@router.get("/redemptions")
def list_redemptions(
    auth: CurrentSession,
    db: DbSession,
    member_id: Annotated[int | None, Query()] = None,
    before: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=HISTORY_PAGE_SIZE)] = HISTORY_PAGE_SIZE,
) -> RedemptionHistoryOut:
    """Einlösungen aller Kinder oder eines Kindes, neueste zuerst."""
    own = child_member_id(db, auth)
    if own is not None:
        if own == 0:
            raise ApiError(status.HTTP_403_FORBIDDEN, "profile.not_linked")
        if member_id is not None:
            ensure_member_access(db, auth, member_id)
        member_id = own
    query = select(RewardRedemption)
    if member_id is not None:
        query = query.where(RewardRedemption.member_id == member_id)
    if before is not None:
        query = query.where(RewardRedemption.id < before)
    redemptions = list(db.scalars(query.order_by(RewardRedemption.id.desc()).limit(limit + 1)))
    cancellations = {
        entry.redemption_id: entry
        for entry in db.scalars(
            select(PointTransaction).where(
                PointTransaction.redemption_id.in_([r.id for r in redemptions[:limit]]),
                PointTransaction.kind == "reward_cancelled",
            )
        )
    }
    return RedemptionHistoryOut(
        redemptions=[redemption_out(r, cancellations.get(r.id)) for r in redemptions[:limit]],
        has_more=len(redemptions) > limit,
    )
