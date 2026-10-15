import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.tasks import get_task
from app.auth import CurrentSession, DbSession, child_member_id, ensure_member_access, get_family
from app.errors import ApiError
from app.models import FamilyMember, Task, TaskCompletion
from app.money import book_money
from app.points import book, earned_on, totals
from app.recurrence import flexible_due
from app.routines import RoutinePlan, Slot
from app.schemas import (
    MemberDueOut,
    MemberPointsOut,
    MemberPositionOut,
    TodayOut,
    TodayTaskOut,
)
from app.today import family_now, time_of_day_at

router = APIRouter(tags=["today"])

# Die Familienansicht ist für alle am Display da: Anmeldung genügt, keine Eltern-PIN.


def due_dates(db: DbSession, tasks: list[Task], day: dt.date) -> dict[int, list[MemberDueOut]]:
    """Fälligkeit flexibler Aufgaben je Person, aus der letzten Erledigung vor heute."""
    flexible = [task for task in tasks if task.recurrence.kind == "flexible"]
    if not flexible:
        return {}
    last: dict[tuple[int, int], dt.date] = {
        (task_id, member_id): date
        for task_id, member_id, date in db.execute(
            select(TaskCompletion.task_id, TaskCompletion.member_id, func.max(TaskCompletion.date))
            .where(
                TaskCompletion.task_id.in_([task.id for task in flexible]),
                TaskCompletion.date < day,
            )
            .group_by(TaskCompletion.task_id, TaskCompletion.member_id)
        )
    }
    result: dict[int, list[MemberDueOut]] = {}
    for task in flexible:
        members = [a.member_id for a in task.assignments]
        if task.shared:
            # Bei „Einer für alle“ zählt die letzte Erledigung durch irgendwen.
            done = [date for (task_id, _), date in last.items() if task_id == task.id]
            due = flexible_due(task.recurrence, max(done, default=None))
            result[task.id] = [MemberDueOut(member_id=m, due_date=due) for m in members]
        else:
            result[task.id] = [
                MemberDueOut(
                    member_id=m, due_date=flexible_due(task.recurrence, last.get((task.id, m)))
                )
                for m in members
            ]
    return result


@router.get("/today")
def get_today(auth: CurrentSession, db: DbSession) -> TodayOut:
    now = family_now(get_family(db))
    day = now.date()
    plan = RoutinePlan(db)
    own = child_member_id(db, auth)
    # Aufgabe → Personen, für die sie heute ansteht (mit ihrem Platz in der Reihenfolge).
    due: dict[int, dict[int, Slot]] = {}
    tasks: list[Task] = []
    for task in db.scalars(select(Task).where(Task.active).order_by(Task.id)):
        members = plan.due_members(task, day)
        if own is not None:
            members = {key: slot for key, slot in members.items() if key == own}
        if members:
            due[task.id] = members
            tasks.append(task)
    done: dict[int, list[int]] = {}
    pending: dict[int, list[int]] = {}
    for task_id, member_id, approved_at in db.execute(
        select(TaskCompletion.task_id, TaskCompletion.member_id, TaskCompletion.approved_at)
        .where(TaskCompletion.date == day)
        .order_by(TaskCompletion.member_id)
    ):
        if own is not None:
            task = db.get(Task, task_id)
            if task and task.shared and own in due.get(task_id, {}):
                member_id = own
            elif member_id != own:
                continue
        done.setdefault(task_id, []).append(member_id)
        if approved_at is None:
            pending.setdefault(task_id, []).append(member_id)
    earned, total = earned_on(db, day), totals(db)
    dues = due_dates(db, tasks, day)
    week_start = day - dt.timedelta(days=day.weekday())

    return TodayOut(
        date=day,
        week_start=week_start,
        time_of_day=time_of_day_at(now.time()),
        tasks=[
            TodayTaskOut(
                id=task.id,
                title=task.title,
                icon=task.icon,
                points=task.points,
                time_of_day=task.time_of_day,
                color=task.color,
                member_ids=list(due[task.id]),
                needs_approval=task.needs_approval,
                repeatable=task.repeatable,
                shared=task.shared,
                extra=task.extra,
                positions=[
                    MemberPositionOut(
                        member_id=member_id,
                        position=slot.position,
                        optional=slot.optional or task.repeatable,
                    )
                    for member_id, slot in due[task.id].items()
                ],
                due_dates=dues.get(task.id, []),
                # Nur Personen, für die die Aufgabe heute (noch) ansteht.
                done_member_ids=sorted(
                    {
                        m
                        for m in (pending if task.repeatable else done).get(task.id, [])
                        if m in due[task.id]
                    }
                ),
                pending_member_ids=sorted(
                    {m for m in pending.get(task.id, []) if m in due[task.id]}
                ),
            )
            for task in tasks
        ],
        points=[
            MemberPointsOut(
                member_id=member_id,
                today=earned.get(member_id, 0),
                total=total.get(member_id, 0),
            )
            for member_id in db.scalars(select(FamilyMember.id).order_by(FamilyMember.id))
            if own is None or member_id == own
        ],
        pending_approvals=db.scalar(
            select(func.count()).where(
                TaskCompletion.approved_at.is_(None),
                *([TaskCompletion.member_id == own] if own is not None else []),
            )
        )
        or 0,
    )


def check_completable(
    db: DbSession, task_id: int, member_id: int, date: dt.date
) -> tuple[Task, dt.date]:
    """Prüft, dass `date` heute ist und die Aufgabe heute für die Person ansteht."""
    today = family_now(get_family(db)).date()
    if date != today:
        # Das Display zeigt noch einen anderen Tag (z. B. kurz nach Mitternacht).
        raise ApiError(status.HTTP_409_CONFLICT, "completion.day_changed")
    task = get_task(db, task_id)
    if RoutinePlan(db).slot(task, member_id, today) is None:
        raise ApiError(status.HTTP_409_CONFLICT, "task.not_due")
    return task, today


@router.put("/today/tasks/{task_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def complete_task(
    task_id: int,
    member_id: int,
    date: dt.date,
    auth: CurrentSession,
    db: DbSession,
    request_key: Annotated[str | None, Query(pattern="^[a-f0-9]{32}$")] = None,
) -> None:
    """Complete once per day, or submit an independently reviewed repeat execution.

    A stable key makes retries idempotent even after approval. Repeatable tasks
    require parent approval and allow only one pending execution at a time.
    """
    ensure_member_access(db, auth, member_id)
    task, today = check_completable(db, task_id, member_id, date)
    # Serialize all executions for this task, including shared tasks and concurrent clients.
    db.execute(select(Task.id).where(Task.id == task_id).with_for_update())
    condition = [TaskCompletion.task_id == task_id, TaskCompletion.date == today]
    if not task.shared:
        condition.append(TaskCompletion.member_id == member_id)
    if task.repeatable:
        if request_key is None:
            raise ApiError(422, "completion.request_key_required")
        used = db.scalar(select(TaskCompletion).where(TaskCompletion.request_key == request_key))
        if used is not None:
            if used.task_id != task_id or used.member_id != member_id or used.date != today:
                raise ApiError(409, "completion.request_key_used")
            db.commit()
            return
        condition.append(TaskCompletion.approved_at.is_(None))
    elif request_key is not None:
        raise ApiError(422, "completion.not_repeatable")
    if db.scalar(select(TaskCompletion.id).where(*condition)) is not None:
        db.commit()
        return
    statement = insert(TaskCompletion).values(
        task_id=task_id,
        member_id=member_id,
        date=today,
        points=task.points,
        money_cents=task.money_cents,
        request_key=request_key,
        approved_at=None if task.needs_approval else func.now(),
    )
    if task.repeatable:
        statement = statement.on_conflict_do_nothing(index_elements=["request_key"])
    else:
        statement = statement.on_conflict_do_nothing(
            index_elements=["task_id", "member_id", "date"],
            index_where=TaskCompletion.request_key.is_(None),
        )
    created = db.scalar(statement.returning(TaskCompletion.id))
    if created is not None and not task.needs_approval:
        book(
            db,
            member_id,
            task.points,
            "task_completed",
            reason=task.title,
            task_id=task_id,
            task_date=today,
        )
    if created is not None and not task.needs_approval:
        book_money(db, member_id, task.money_cents, "task_completed", task.title, created)
    db.commit()


@router.delete("/today/tasks/{task_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo_task(
    task_id: int, member_id: int, date: dt.date, auth: CurrentSession, db: DbSession
) -> None:
    """Macht die heutige Erledigung rückgängig und bucht ihre Punkte zurück (Gegenbuchung).

    War sie nicht erledigt, passiert nichts; war sie noch ungeprüft, gibt es nichts zurückzubuchen.
    Bei „Einer für alle“ nimmt jede zugeordnete Person die Erledigung zurück, egal wer sie war;
    die Gegenbuchung trifft die Person, die sie erledigt hatte.
    """
    ensure_member_access(db, auth, member_id)
    task, today = check_completable(db, task_id, member_id, date)
    db.execute(select(Task.id).where(Task.id == task_id).with_for_update())
    condition = [TaskCompletion.task_id == task_id, TaskCompletion.date == today]
    if not task.shared:
        condition.append(TaskCompletion.member_id == member_id)
    # Approved repeat executions remain historical; only cancel the current pending execution.
    if task.repeatable:
        condition.append(TaskCompletion.approved_at.is_(None))
    removed = db.execute(
        delete(TaskCompletion)
        .where(*condition)
        .returning(
            TaskCompletion.member_id,
            TaskCompletion.points,
            TaskCompletion.approved_at,
            TaskCompletion.money_cents,
            TaskCompletion.id,
        )
    ).all()
    # Mehrere Zeilen nur, wenn eine Aufgabe erst nachträglich auf „Einer für alle“ gestellt wurde.
    for completion in removed:
        if completion.approved_at is None:
            continue
        book_money(
            db,
            completion.member_id,
            -completion.money_cents,
            "task_undone",
            task.title,
            completion.id,
        )
        book(
            db,
            completion.member_id,
            -completion.points,
            "task_undone",
            reason=task.title,
            task_id=task_id,
            task_date=today,
        )
    db.commit()
