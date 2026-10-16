"""Read-only consistency findings. No inference here authorizes a data correction."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_family
from app.models import (
    Chore,
    ChoreCompletion,
    FamilyMember,
    PenaltyReversal,
    PointTransaction,
    Praise,
    Reward,
    RewardRedemption,
    Task,
)
from app.points import balance, level_xp
from app.today import family_now, utcnow


def consistency_report(db: Session) -> dict:
    findings = []

    def add(code, entity, record_id, detail, severity="review"):
        findings.append(
            dict(code=code, entity=entity, id=record_id, detail=detail, severity=severity)
        )

    members = list(db.scalars(select(FamilyMember).order_by(FamilyMember.id)))
    children = {m.id for m in members if m.role == "child"}
    summaries = [
        dict(
            member_id=m.id,
            spendable_stars=balance(db, m.id),
            earned_level_xp=level_xp(db, m.id),
            highest_level=m.highest_level,
        )
        for m in members
    ]
    for row in summaries:
        if row["spendable_stars"] < 0:
            add("negative_balance", "member", row["member_id"], row, "error")
    entries = list(db.scalars(select(PointTransaction).order_by(PointTransaction.id)))
    by_id = {e.id: e for e in entries}
    reversals = list(db.scalars(select(PenaltyReversal)))
    reversed_ids = {r.transaction_id for r in reversals}
    linked_ids = {r.refund_transaction_id for r in reversals}
    for reversal in reversals:
        original, refund = (
            by_id.get(reversal.transaction_id),
            by_id.get(reversal.refund_transaction_id),
        )
        if (
            not original
            or not refund
            or original.kind != "manual"
            or original.member_id != refund.member_id
            or original.amount != -refund.amount
        ):
            add(
                "invalid_reversal_link",
                "point_transaction",
                reversal.transaction_id,
                {"refund_transaction_id": reversal.refund_transaction_id},
                "error",
            )
    for entry in entries:
        if entry.kind in ("penalty_reversed", "manual_reversed") and entry.id not in linked_ids:
            add("unlinked_refund", "point_transaction", entry.id, {}, "error")
        if entry.kind == "manual" and entry.amount < 0:
            candidates = [
                e.id
                for e in entries
                if e.member_id == entry.member_id
                and e.kind == "manual"
                and e.amount == -entry.amount
                and e.id > entry.id
                and e.id not in linked_ids
                and e.id not in reversed_ids
            ]
            if candidates:
                add(
                    "possible_manual_compensation",
                    "point_transaction",
                    entry.id,
                    {
                        "candidate_ids": candidates,
                        "already_reversed": entry.id in reversed_ids,
                        "note": "Matching amounts alone do not establish a duplicate refund.",
                    },
                )
        if entry.reason and "test" in entry.reason.casefold() and entry.id not in reversed_ids:
            add(
                "possible_test_booking",
                "point_transaction",
                entry.id,
                {"member_id": entry.member_id, "amount": entry.amount},
            )
    for praise in db.scalars(select(Praise).where(Praise.revoked_at.is_(None))):
        if "test" in praise.reason.casefold():
            add("possible_test_praise", "praise", praise.id, {"member_id": praise.member_id})
    last_done = dict(
        db.execute(
            select(ChoreCompletion.chore_id, func.max(ChoreCompletion.date))
            .where(ChoreCompletion.approved.is_(True))
            .group_by(ChoreCompletion.chore_id)
        ).all()
    )
    day = family_now(get_family(db)).date()
    for chore in db.scalars(select(Chore).order_by(Chore.id)):
        invalid = [member_id for member_id in chore.child_member_ids if member_id not in children]
        if invalid:
            add("invalid_child_assignment", "chore", chore.id, {"member_ids": invalid}, "error")
        if chore.child_enabled and not chore.child_member_ids:
            add(
                "empty_child_assignment",
                "chore",
                chore.id,
                {"note": "Empty means no selected child. Review intended assignment."},
            )
        due = last_done.get(chore.id, chore.anchor_date) + dt.timedelta(days=chore.interval_days)
        if chore.active and (day - due).days >= 90:
            add(
                "long_overdue",
                "chore",
                chore.id,
                {
                    "due_date": due.isoformat(),
                    "note": "Overdue is not a data error; may be intentional or imported.",
                },
                "info",
            )
    tasks = {t.id: t for t in db.scalars(select(Task))}
    for entry in entries:
        task = tasks.get(entry.task_id)
        if task and entry.kind == "task_completed" and entry.amount != task.points:
            add(
                "historical_task_snapshot",
                "point_transaction",
                entry.id,
                {"booked": entry.amount, "current": task.points},
                "info",
            )
    rewards = {r.id: r for r in db.scalars(select(Reward))}
    for redemption in db.scalars(select(RewardRedemption).order_by(RewardRedemption.id)):
        reward = rewards.get(redemption.reward_id)
        if reward and reward.cost != redemption.cost:
            add(
                "historical_reward_snapshot",
                "redemption",
                redemption.id,
                {"booked": redemption.cost, "current": reward.cost},
                "info",
            )
    return dict(
        generated_at=utcnow(),
        read_only=True,
        members=summaries,
        findings=findings,
        note="Stars and level XP differ; historical prices are retained.",
    )
