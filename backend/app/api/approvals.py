from fastapi import APIRouter, Query, status
from sqlalchemy import delete, func, select, update

from app.auth import DbSession, ParentSession
from app.errors import ApiError
from app.models import Chore, ChoreCompletion, Task, TaskCompletion
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
