"""One paginated family-member activity list, with exact correction targets."""

import base64
import datetime as dt
import json

from sqlalchemy import and_, func, literal, or_, select, union_all

from app.errors import ApiError
from app.models import (
    ActivityCorrection,
    ActivityJournalLink,
    Chore,
    ChoreCompletion,
    ChoreCredit,
    MoneyTransaction,
    PenaltyReversal,
    PointTransaction,
    TaskCompletion,
)
from app.points import balance


def _active_completion(db, entry):
    source, origin = entry.completion_source, entry.completion_id
    if source is None and entry.kind in ("task_completed", "chore_completed"):
        # Old rows: only a unique credit and completion in the SAME database transaction
        # are usable. Never match titles, amounts or dates alone.
        group = [
            PointTransaction.member_id == entry.member_id,
            PointTransaction.kind == entry.kind,
            PointTransaction.created_at == entry.created_at,
        ]
        if db.scalar(select(func.count()).select_from(PointTransaction).where(*group)) != 1:
            return None
        if entry.kind == "task_completed":
            candidates = list(
                db.scalars(
                    select(TaskCompletion).where(
                        TaskCompletion.task_id == entry.task_id,
                        TaskCompletion.member_id == entry.member_id,
                        TaskCompletion.date == entry.task_date,
                        TaskCompletion.points == entry.amount,
                        TaskCompletion.approved_at == entry.created_at,
                    )
                )
            )
            source = "task"
        else:
            candidates = list(
                db.scalars(
                    select(ChoreCompletion)
                    .join(
                        ChoreCredit,
                        ChoreCredit.completion_id == ChoreCompletion.id,
                    )
                    .where(
                        ChoreCompletion.member_id == entry.member_id,
                        ChoreCompletion.date == entry.task_date,
                        ChoreCompletion.completed_at == entry.created_at,
                        ChoreCredit.member_id == entry.member_id,
                        ChoreCredit.amount == entry.amount,
                        ChoreCompletion.approved.is_(True),
                    )
                )
            )
            source = "chore"
        if len(candidates) != 1:
            return None
        origin = candidates[0].id
    if source not in ("task", "chore") or origin is None:
        return None
    if entry.kind != f"{source}_completed":
        return None
    model = TaskCompletion if source == "task" else ChoreCompletion
    completion = db.get(model, origin)
    if completion is None or completion.member_id != entry.member_id:
        return None
    if completion.date != entry.task_date:
        return None
    if source == "task":
        if completion.task_id != entry.task_id:
            return None
        if completion.approved_at is None or completion.points != entry.amount:
            return None
    else:
        credit = db.get(ChoreCredit, origin)
        if not completion.approved or credit is None:
            return None
        if credit.member_id != entry.member_id or credit.amount != entry.amount:
            return None
        newest = db.scalar(
            select(func.max(PointTransaction.id)).where(
                PointTransaction.completion_source == "chore",
                PointTransaction.completion_id == origin,
                PointTransaction.kind == "chore_completed",
            )
        )
        if newest is not None and newest != entry.id:
            return None
    return source, origin


def activity_history(db, member_id, cursor=None, limit=50):
    from app.api.points import transaction_out

    points = select(
        literal("point").label("source"),
        PointTransaction.id.label("id"),
        PointTransaction.created_at.label("occurred_at"),
    ).where(
        PointTransaction.member_id == member_id,
        ~select(ActivityJournalLink.journal_id)
        .where(
            ActivityJournalLink.journal_source == "point",
            ActivityJournalLink.journal_id == PointTransaction.id,
        )
        .exists(),
    )
    zero_tasks = select(
        literal("task").label("source"),
        TaskCompletion.id.label("id"),
        TaskCompletion.approved_at.label("occurred_at"),
    ).where(
        TaskCompletion.member_id == member_id,
        TaskCompletion.approved_at.is_not(None),
        TaskCompletion.points == 0,
        TaskCompletion.money_cents == 0,
        ~select(ActivityCorrection.id)
        .where(
            ActivityCorrection.source == "task",
            ActivityCorrection.origin_id == TaskCompletion.id,
            ActivityCorrection.member_id == member_id,
        )
        .exists(),
    )
    zero_chores = (
        select(
            literal("chore").label("source"),
            ChoreCompletion.id.label("id"),
            ChoreCompletion.completed_at.label("occurred_at"),
        )
        .outerjoin(ChoreCredit, ChoreCredit.completion_id == ChoreCompletion.id)
        .where(
            ChoreCompletion.member_id == member_id,
            ChoreCompletion.approved.is_(True),
            ChoreCredit.completion_id.is_(None),
            ~select(ActivityCorrection.id)
            .where(
                ActivityCorrection.source == "chore",
                ActivityCorrection.origin_id == ChoreCompletion.id,
                ActivityCorrection.member_id == member_id,
            )
            .exists(),
        )
    )
    money_only = select(
        literal("money").label("source"),
        MoneyTransaction.id.label("id"),
        MoneyTransaction.created_at.label("occurred_at"),
    ).where(
        MoneyTransaction.member_id == member_id,
        MoneyTransaction.kind.in_(("task_completed", "task_undone")),
        ~select(ActivityJournalLink.journal_id)
        .where(
            ActivityJournalLink.journal_source == "money",
            ActivityJournalLink.journal_id == MoneyTransaction.id,
        )
        .exists(),
        ~select(PointTransaction.id)
        .where(
            PointTransaction.member_id == MoneyTransaction.member_id,
            PointTransaction.kind == MoneyTransaction.kind,
            PointTransaction.created_at == MoneyTransaction.created_at,
        )
        .exists(),
    )
    states = select(
        literal("state").label("source"),
        ActivityCorrection.id.label("id"),
        ActivityCorrection.occurred_at.label("occurred_at"),
    ).where(ActivityCorrection.member_id == member_id)
    feed = union_all(points, zero_tasks, zero_chores, money_only, states).subquery()
    query = select(feed)
    if cursor:
        try:
            stamp, source, origin = json.loads(
                base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
            )
            stamp = dt.datetime.fromisoformat(stamp)
            if stamp.tzinfo is None or source not in ("point", "task", "chore", "money", "state"):
                raise ValueError
            if not isinstance(origin, int) or isinstance(origin, bool) or origin < 1:
                raise ValueError
        except (ValueError, TypeError, OverflowError, UnicodeError):
            raise ApiError(422, "validation.invalid") from None
        query = query.where(
            or_(
                feed.c.occurred_at < stamp,
                and_(feed.c.occurred_at == stamp, feed.c.source < source),
                and_(feed.c.occurred_at == stamp, feed.c.source == source, feed.c.id < origin),
            )
        )
    rows = list(
        db.execute(
            query.order_by(
                feed.c.occurred_at.desc(),
                feed.c.source.desc(),
                feed.c.id.desc(),
            ).limit(limit + 1)
        ).mappings()
    )
    items = []
    point_ids = [row["id"] for row in rows[:limit] if row["source"] == "point"]
    reversals = {
        r.transaction_id: r
        for r in db.scalars(
            select(PenaltyReversal).where(
                PenaltyReversal.transaction_id.in_(point_ids),
            )
        )
    }
    compensations = {
        r.refund_transaction_id: r.transaction_id
        for r in db.scalars(
            select(PenaltyReversal).where(PenaltyReversal.refund_transaction_id.in_(point_ids)),
        )
    }
    for row in rows[:limit]:
        source, origin = row["source"], row["id"]
        if source == "state":
            state = db.get(ActivityCorrection, origin)
            if state is None:
                continue
            available = not state.inactive
            if state.source in ("task", "chore"):
                model = TaskCompletion if state.source == "task" else ChoreCompletion
                completion = db.get(model, state.origin_id)
                available = (
                    available and completion is not None and completion.member_id == member_id
                )
                if available and state.source == "chore" and state.snapshot["point_amount"]:
                    credit = db.get(ChoreCredit, state.origin_id)
                    available = credit is not None and credit.member_id == member_id
            item = dict(
                id=-4 * origin,
                amount=state.snapshot["point_amount"],
                money_cents=state.snapshot["money_cents"],
                kind="manual" if state.source == "manual" else f"{state.source}_completed",
                reason=state.title,
                icon=state.icon,
                task_date=state.snapshot.get("completion", {}).get("date"),
                created_at=state.occurred_at,
                inactive=state.inactive,
                correction_id=state.id,
                restore_id=state.id if state.inactive else None,
                reactivated=not state.inactive and state.restored_at is not None,
                undo_source=state.source if available and state.source != "manual" else None,
                undo_id=state.origin_id if available and state.source != "manual" else None,
            )
        elif source == "point":
            entry = db.get(PointTransaction, origin)
            if entry is None:
                continue
            item = transaction_out(
                entry, reversals.get(origin), compensations.get(origin)
            ).model_dump()
            target = _active_completion(db, entry)
            item.update(
                undo_source=target[0] if target else None, undo_id=target[1] if target else None
            )
        elif source == "money":
            entry = db.get(MoneyTransaction, origin)
            if entry is None:
                continue
            c = db.get(TaskCompletion, entry.completion_id) if entry.completion_id else None
            available = (
                entry.kind == "task_completed"
                and c is not None
                and c.approved_at is not None
                and c.member_id == member_id
            )
            item = dict(
                id=-4 * origin - 3,
                amount=0,
                money_cents=entry.amount_cents,
                kind=entry.kind,
                reason=entry.reason,
                icon=c.task.icon if c else None,
                task_date=c.date if c else None,
                created_at=entry.created_at,
                undo_source="task" if available else None,
                undo_id=c.id if available else None,
            )
        else:
            model = TaskCompletion if source == "task" else ChoreCompletion
            c = db.get(model, origin)
            if c is None:
                continue
            definition = c.task if source == "task" else db.get(Chore, c.chore_id)
            if definition is None:
                continue
            item = dict(
                id=-4 * origin - (2 if source == "chore" else 1),
                amount=0,
                kind=f"{source}_completed",
                reason=definition.title,
                icon=definition.icon,
                task_date=c.date,
                created_at=row["occurred_at"],
                undo_source=source,
                undo_id=origin,
            )
        items.append(item)
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        value = [last["occurred_at"].isoformat(), last["source"], last["id"]]
        next_cursor = base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return dict(
        total=balance(db, member_id),
        transactions=items,
        has_more=len(rows) > limit,
        next_cursor=next_cursor,
    )
