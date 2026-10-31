from fastapi import APIRouter, Query, status
from sqlalchemy import delete, func, select, update

from app.auth import DbSession, ParentSession
from app.errors import ApiError
from app.models import Chore, ChoreCompletion, ChoreCredit, Task, TaskCompletion
from app.money import book_money
from app.points import book
from app.schemas import ApprovalOut

router = APIRouter(tags=["approvals"])

# Kontrolle durch die Eltern: ungeprüfte Erledigungen bestätigen (Punkte buchen) oder ablehnen
# (Erledigung löschen, die Aufgabe ist wieder offen). Später auch per PWA am Smartphone.


@router.get("/approvals", response_model_exclude_defaults=True)
def list_approvals(_: ParentSession, db: DbSession) -> list[ApprovalOut]:
    """Ungeprüfte Erledigungen aller Tage, älteste zuerst."""
    completions = db.scalars(
        select(TaskCompletion)
        .where(TaskCompletion.approved_at.is_(None))
        .order_by(TaskCompletion.completed_at, TaskCompletion.id)
    )
    result = [
        ApprovalOut(
            id=completion.id,
            task_id=completion.task_id,
            title=completion.task.title,
            icon=completion.task.icon,
            points=completion.points,
            member_id=completion.member_id,
            date=completion.date,
            completed_at=completion.completed_at,
        )
        for completion in completions
    ]
    for completion, chore in db.execute(
        select(ChoreCompletion, Chore)
        .join(Chore)
        .where(ChoreCompletion.approved.is_(False), ChoreCompletion.member_id.is_not(None))
    ):
        result.append(
            ApprovalOut(
                id=completion.id,
                source="chore",
                task_id=chore.id,
                title=chore.title,
                icon=chore.icon,
                points=completion.points,
                member_id=completion.member_id,
                date=completion.date,
                completed_at=completion.completed_at,
            )
        )
    return sorted(result, key=lambda item: (item.completed_at, item.id))


@router.post("/approvals/{completion_id}", status_code=status.HTTP_204_NO_CONTENT)
def approve(
    completion_id: int,
    auth_session: ParentSession,
    db: DbSession,
    praise: bool = Query(default=False),
) -> None:
    """Bestätigt die Erledigung und bucht ihre Punkte, genau einmal (auch bei Doppel-Tipp)."""
    # Keep the same task -> completion -> member lock order as completion and undo.
    # Otherwise an approval holding the completion can wait for the task FK while
    # a correction holding the task waits for that completion.
    task_id = db.scalar(select(TaskCompletion.task_id).where(TaskCompletion.id == completion_id))
    if task_id is not None:
        db.execute(select(Task.id).where(Task.id == task_id).with_for_update())
    approved = db.execute(
        update(TaskCompletion)
        .where(TaskCompletion.id == completion_id, TaskCompletion.approved_at.is_(None))
        .values(approved_at=func.now(), approved_by_user_id=auth_session.user_id)
        .returning(
            TaskCompletion.task_id,
            TaskCompletion.member_id,
            TaskCompletion.date,
            TaskCompletion.points,
            TaskCompletion.money_cents,
            TaskCompletion.id,
        )
    ).first()
    if approved is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    title = db.scalar(select(Task.title).where(Task.id == approved.task_id))
    book(
        db,
        approved.member_id,
        approved.points,
        "task_completed",
        reason=title,
        task_id=approved.task_id,
        task_date=approved.date,
        user_id=auth_session.user_id,
        completion_source="task",
        completion_id=approved.id,
    )
    book_money(
        db,
        approved.member_id,
        approved.money_cents,
        "task_completed",
        title or "Aufgabe",
        approved.id,
    )
    if praise:
        from app.praise import grant_praise

        grant_praise(
            db,
            approved.member_id,
            auth_session.user_id,
            title or "Aufgabe",
            f"task:{completion_id}",
        )
    db.commit()


@router.delete("/approvals/{completion_id}", status_code=status.HTTP_204_NO_CONTENT)
def reject(completion_id: int, _: ParentSession, db: DbSession) -> None:
    """Lehnt die Erledigung ab: Sie wird gelöscht, die Aufgabe ist wieder offen."""
    rejected = db.scalar(
        delete(TaskCompletion)
        .where(TaskCompletion.id == completion_id, TaskCompletion.approved_at.is_(None))
        .returning(TaskCompletion.id)
    )
    if rejected is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    db.commit()


@router.post("/chore-approvals/{completion_id}", status_code=status.HTTP_204_NO_CONTENT)
def approve_chore(
    completion_id: int,
    _: ParentSession,
    db: DbSession,
    praise: bool = Query(default=False),
) -> None:
    from app.api.chores import _get_chore
    from app.models import ChoreCredit
    from app.points import lock_member

    completion = db.get(ChoreCompletion, completion_id)
    if completion is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    chore = _get_chore(db, completion.chore_id)
    completion = db.scalar(
        select(ChoreCompletion)
        .where(ChoreCompletion.id == completion_id)
        .execution_options(populate_existing=True)
    )
    if completion is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    if completion.approved:
        return
    completion.approved = True
    if completion.member_id is not None and completion.points:
        lock_member(db, completion.member_id)
        book(
            db,
            completion.member_id,
            completion.points,
            "chore_completed",
            reason=chore.title,
            task_date=completion.date,
            user_id=_.user_id,
            completion_source="chore",
            completion_id=completion.id,
        )
        db.add(
            ChoreCredit(
                completion_id=completion.id,
                member_id=completion.member_id,
                amount=completion.points,
            )
        )
    if praise and completion.member_id is not None:
        from app.praise import grant_praise

        grant_praise(db, completion.member_id, _.user_id, chore.title, f"chore:{completion_id}")
    db.commit()


@router.delete("/chore-approvals/{completion_id}", status_code=status.HTTP_204_NO_CONTENT)
def reject_chore(completion_id: int, _: ParentSession, db: DbSession) -> None:
    from app.api.chores import _get_chore

    completion = db.get(ChoreCompletion, completion_id)
    if completion is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    _get_chore(db, completion.chore_id)
    completion = db.scalar(
        select(ChoreCompletion)
        .where(ChoreCompletion.id == completion_id)
        .execution_options(populate_existing=True)
    )
    if completion is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "approval.not_found")
    if not completion.approved:
        db.delete(completion)
        db.commit()


@router.get("/chore-approvals/confirmed")
def confirmed_chores(
    _: ParentSession,
    db: DbSession,
    before: int | None = Query(default=None, ge=1),
    member_id: int | None = Query(default=None, ge=1),
) -> dict:
    """Confirmed household executions, newest first, including earlier days."""
    query = (
        select(ChoreCompletion, Chore, ChoreCredit)
        .join(Chore)
        .outerjoin(ChoreCredit, ChoreCredit.completion_id == ChoreCompletion.id)
        .where(ChoreCompletion.approved.is_(True), ChoreCompletion.member_id.is_not(None))
        .order_by(ChoreCompletion.id.desc())
        .limit(51)
    )
    if before is not None:
        query = query.where(ChoreCompletion.id < before)
    if member_id is not None:
        query = query.where(ChoreCompletion.member_id == member_id)
    rows = list(db.execute(query))
    return {
        "items": [
            ApprovalOut(
                id=c.id,
                source="chore",
                task_id=chore.id,
                title=chore.title,
                icon=chore.icon,
                points=credit.amount if credit else 0,
                member_id=c.member_id,
                date=c.date,
                completed_at=c.completed_at,
            )
            for c, chore, credit in rows[:50]
        ],
        "has_more": len(rows) > 50,
    }


@router.delete("/chore-approvals/{completion_id}/confirmed", status_code=204)
def undo_confirmed_chore(completion_id: int, auth: ParentSession, db: DbSession) -> None:
    """Remove exactly one execution and reverse its original credit once."""
    from app.api.chores import _get_chore, _reverse_chore_credits

    old = db.get(ChoreCompletion, completion_id)
    if old is None:
        return
    chore = _get_chore(db, old.chore_id)
    completion = db.scalar(
        select(ChoreCompletion)
        .where(ChoreCompletion.id == completion_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if completion is None:
        return
    if not completion.approved:
        raise ApiError(status.HTTP_409_CONFLICT, "approval.not_found")
    _reverse_chore_credits(db, [completion], chore.title)
    db.delete(completion)
    db.commit()


@router.get("/approvals/confirmed")
def confirmed_tasks(
    _: ParentSession,
    db: DbSession,
    before: int | None = Query(default=None, ge=1),
    member_id: int | None = Query(default=None, ge=1),
) -> dict:
    """Confirmed child tasks, paginated and filtered before applying the limit."""
    query = (
        select(TaskCompletion, Task)
        .join(Task)
        .where(TaskCompletion.approved_at.is_not(None))
        .order_by(TaskCompletion.id.desc())
        .limit(51)
    )
    if before is not None:
        query = query.where(TaskCompletion.id < before)
    if member_id is not None:
        query = query.where(TaskCompletion.member_id == member_id)
    rows = list(db.execute(query))
    return {
        "items": [
            ApprovalOut(
                id=c.id,
                task_id=task.id,
                title=task.title,
                icon=task.icon,
                points=c.points,
                member_id=c.member_id,
                date=c.date,
                completed_at=c.completed_at,
            )
            for c, task in rows[:50]
        ],
        "has_more": len(rows) > 50,
    }


@router.delete("/approvals/{completion_id}/confirmed", status_code=204)
def undo_confirmed_task(completion_id: int, auth: ParentSession, db: DbSession) -> None:
    """Reverse exactly one execution using its original point and bonus snapshots."""
    from app.points import lock_member

    old = db.get(TaskCompletion, completion_id)
    if old is None:
        return
    # Same task lock as completion creation; refresh after waiting for concurrent actions.
    task_id = old.task_id
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update(of=Task))
    completion = db.scalar(
        select(TaskCompletion)
        .where(TaskCompletion.id == completion_id)
        .execution_options(populate_existing=True)
        .with_for_update(of=TaskCompletion)
    )
    if completion is None:
        return
    if completion.approved_at is None:
        raise ApiError(409, "approval.not_found")
    if db.info.get("mcp_request") and completion.money_cents:
        raise ApiError(403, "mcp.operation_forbidden")
    lock_member(db, completion.member_id)
    title = task.title if task else "Aufgabe"
    book(
        db,
        completion.member_id,
        -completion.points,
        "task_undone",
        reason=title,
        task_id=task_id,
        task_date=completion.date,
        user_id=auth.user_id,
    )
    book_money(
        db,
        completion.member_id,
        -completion.money_cents,
        "task_undone",
        title,
        completion.id,
    )
    db.delete(completion)
    db.commit()
