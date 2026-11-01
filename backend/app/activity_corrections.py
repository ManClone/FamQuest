"""Reversible activation of frozen executions; journals remain append-only."""

import datetime as dt

from sqlalchemy import select

from app.errors import ApiError
from app.models import (
    ActivityCorrection,
    ActivityJournalLink,
    Chore,
    ChoreCompletion,
    ChoreCredit,
    MoneyTransaction,
    PointTransaction,
    Task,
    TaskCompletion,
)
from app.money import book_money
from app.points import balance, book, lock_member


def link_journal(db, state, source, entry_id):
    if entry_id is None:
        return
    existing = db.get(ActivityJournalLink, (source, entry_id))
    if existing is not None:
        if existing.correction_id != state.id:
            raise ApiError(409, "activity.already_grouped")
        return
    db.add(ActivityJournalLink(journal_source=source, journal_id=entry_id, correction_id=state.id))


def _existing(db, source, origin, member):
    return db.scalar(
        select(ActivityCorrection)
        .where(
            ActivityCorrection.source == source,
            ActivityCorrection.origin_id == origin,
            ActivityCorrection.member_id == member,
        )
        .with_for_update()
    )


def capture_completion(db, source, completion, definition, actor_id):
    from app.activity import _active_completion

    credit = db.get(ChoreCredit, completion.id) if source == "chore" else None
    member = credit.member_id if credit else completion.member_id
    if member is None:
        raise ApiError(409, "activity.restore_unavailable")
    lock_member(db, member)
    state = _existing(db, source, completion.id, member)
    if state is not None:
        return state
    amount = completion.points if source == "task" else credit.amount if credit else 0
    values = {}
    for column in completion.__table__.columns:
        value = getattr(completion, column.key)
        values[column.key] = (
            value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else value
        )
    values["member_id"] = member
    candidates = (
        list(
            db.scalars(
                select(PointTransaction)
                .where(
                    PointTransaction.member_id == member,
                    PointTransaction.kind == f"{source}_completed",
                    PointTransaction.amount == amount,
                )
                .order_by(PointTransaction.id.desc())
            )
        )
        if amount
        else []
    )
    original = next(
        (p for p in candidates if _active_completion(db, p) == (source, completion.id)), None
    )
    money = db.scalar(
        select(MoneyTransaction)
        .where(
            MoneyTransaction.member_id == member,
            MoneyTransaction.completion_id == completion.id,
            MoneyTransaction.kind == f"{source}_completed",
        )
        .order_by(MoneyTransaction.id.desc())
    )
    state = ActivityCorrection(
        source=source,
        origin_id=completion.id,
        member_id=member,
        title=original.reason if original and original.reason else definition.title,
        icon=definition.icon,
        occurred_at=original.created_at
        if original
        else money.created_at
        if money
        else completion.approved_at
        if source == "task"
        else completion.completed_at,
        snapshot=dict(
            completion=values,
            point_amount=amount,
            money_cents=completion.money_cents,
            shared=bool(definition.shared) if source == "task" else False,
        ),
        inactive=False,
        changed_by_user_id=actor_id,
    )
    db.add(state)
    db.flush()
    link_journal(db, state, "point", original.id if original else None)
    link_journal(db, state, "money", money.id if money else None)
    return state


def _book_money(db, state, amount, kind):
    if not amount:
        return
    book_money(db, state.member_id, amount, kind, state.title, state.origin_id)
    db.flush()
    entry_id = db.scalar(
        select(MoneyTransaction.id)
        .where(
            MoneyTransaction.member_id == state.member_id,
            MoneyTransaction.completion_id == state.origin_id,
            MoneyTransaction.kind == kind,
        )
        .order_by(MoneyTransaction.id.desc())
    )
    link_journal(db, state, "money", entry_id)


def reverse_completion(db, source, completion, definition, actor_id):
    state = capture_completion(db, source, completion, definition, actor_id)
    if state.inactive:
        return state
    amount = state.snapshot["point_amount"]
    entry = book(
        db,
        state.member_id,
        -amount,
        f"{source}_undone",
        reason=state.title,
        task_id=completion.task_id if source == "task" else None,
        task_date=completion.date,
        user_id=actor_id,
    )
    link_journal(db, state, "point", entry.id if entry else None)
    if db.info.get("mcp_request") and state.snapshot["money_cents"]:
        raise ApiError(403, "mcp.operation_forbidden")
    _book_money(db, state, -state.snapshot["money_cents"], f"{source}_undone")
    if source == "chore":
        credit = db.get(ChoreCredit, completion.id)
        if credit is not None:
            db.delete(credit)
            db.flush()
    state.inactive = True
    state.changed_by_user_id = actor_id
    db.delete(completion)
    db.flush()
    return state


def capture_manual(db, entry, member_id, actor_id):
    if entry is None or entry.member_id != member_id or entry.kind != "manual" or entry.amount <= 0:
        return None
    state = _existing(db, "manual", entry.id, member_id)
    if state is not None:
        return state
    state = ActivityCorrection(
        source="manual",
        origin_id=entry.id,
        member_id=member_id,
        title=entry.reason or "Gutschrift",
        icon=None,
        occurred_at=entry.created_at,
        snapshot=dict(point_amount=entry.amount, money_cents=0),
        inactive=False,
        changed_by_user_id=actor_id,
    )
    db.add(state)
    db.flush()
    link_journal(db, state, "point", entry.id)
    return state


def finish_manual_reverse(db, state, refund_id, actor_id):
    if state is None:
        return
    link_journal(db, state, "point", refund_id)
    # A retry of the original reverse request must not undo a later restoration.
    if state.restored_at is None or state.inactive:
        state.inactive = True
        state.changed_by_user_id = actor_id


def _locked_state(db, correction_id):
    old = db.get(ActivityCorrection, correction_id)
    if old is None:
        raise ApiError(404, "common.not_found")
    if db.info.get("mcp_request"):
        raise ApiError(403, "mcp.operation_forbidden")
    if old.source in ("task", "chore"):
        model = Task if old.source == "task" else Chore
        column = "task_id" if old.source == "task" else "chore_id"
        definition_id = old.snapshot["completion"][column]
        db.execute(select(model.id).where(model.id == definition_id).with_for_update())
    lock_member(db, old.member_id)
    return db.scalar(
        select(ActivityCorrection)
        .where(ActivityCorrection.id == correction_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def restore(db, correction_id, actor_id):
    state = _locked_state(db, correction_id)
    if not state.inactive:
        return
    if state.source == "manual":
        entry = book(
            db,
            state.member_id,
            state.snapshot["point_amount"],
            "manual",
            reason=state.title,
            user_id=actor_id,
        )
        db.flush()
        link_journal(db, state, "point", entry.id if entry else None)
    else:
        values = dict(state.snapshot["completion"])
        source = state.source
        model = TaskCompletion if source == "task" else ChoreCompletion
        definition_model = Task if source == "task" else Chore
        column = "task_id" if source == "task" else "chore_id"
        definition = db.get(definition_model, values[column])
        if definition is None:
            raise ApiError(409, "activity.restore_unavailable")
        if db.get(model, state.origin_id) is not None:
            raise ApiError(409, "activity.restore_conflict")
        day = dt.date.fromisoformat(values["date"])
        conditions = [getattr(model, column) == values[column]]
        key = values.get("request_key")
        if key is not None:
            collision = db.scalar(select(model.id).where(model.request_key == key))
            if collision is not None:
                raise ApiError(409, "activity.restore_conflict")
        if key is None or not definition.repeatable:
            conditions.append(model.date == day)
            if source == "task" and not (definition.shared or state.snapshot.get("shared")):
                conditions.append(model.member_id == state.member_id)
            if db.scalar(select(model.id).where(*conditions)) is not None:
                raise ApiError(409, "activity.restore_conflict")
        values["date"] = day
        for column in ("completed_at", "approved_at"):
            if values.get(column):
                values[column] = dt.datetime.fromisoformat(values[column])
        if source == "task":
            values["approved_by_user_id"] = actor_id
        completion = model(**values)
        db.add(completion)
        db.flush()
        entry = book(
            db,
            state.member_id,
            state.snapshot["point_amount"],
            f"{source}_completed",
            reason=state.title,
            task_id=values.get("task_id"),
            task_date=day,
            user_id=actor_id,
            completion_source=source,
            completion_id=state.origin_id,
        )
        link_journal(db, state, "point", entry.id if entry else None)
        _book_money(db, state, state.snapshot["money_cents"], f"{source}_completed")
        if source == "chore" and state.snapshot["point_amount"]:
            db.add(
                ChoreCredit(
                    completion_id=state.origin_id,
                    member_id=state.member_id,
                    amount=state.snapshot["point_amount"],
                )
            )
    state.inactive = False
    state.restored_at = dt.datetime.now(dt.UTC)
    state.changed_by_user_id = actor_id
    db.flush()


def deactivate_manual(db, correction_id, actor_id, reason):
    state = _locked_state(db, correction_id)
    if state.source != "manual":
        raise ApiError(422, "validation.invalid")
    if state.inactive:
        return
    if balance(db, state.member_id) < state.snapshot["point_amount"]:
        raise ApiError(409, "points.insufficient")
    entry = book(
        db,
        state.member_id,
        -state.snapshot["point_amount"],
        "manual_reversed",
        reason=reason,
        user_id=actor_id,
    )
    db.flush()
    link_journal(db, state, "point", entry.id if entry else None)
    state.inactive = True
    state.changed_by_user_id = actor_id
