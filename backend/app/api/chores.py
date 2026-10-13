"""Putzplan: wiederkehrende Hausarbeit mit Ampel statt festem Termin.

Erledigen geht am Display ohne Eltern-PIN, wie bei Essensplan und Einkaufsliste; wer es war, ist
freiwillig. Räume und Aufgaben verwalten die Eltern im Elternbereich, von Hand oder über den
Einrichtungs-Assistenten (`POST /chores/setup`). Zum Haushalt gehört auch die Liste „Zu erledigen“
(siehe api/todos); sie kommt hier mit, damit alle Ansichten denselben Stand zeigen.
"""

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.members import get_member
from app.api.todos import TodoOut, todo_out, todo_shares, visible_todos
from app.auth import CurrentSession, DbSession, ParentSession, get_family, is_parent_unlocked
from app.chores import chore_state
from app.errors import ApiError
from app.household_assignment import HouseholdChore, suggest_week
from app.models import Chore, ChoreCompletion, ChoreCredit, ChoreRoom, FamilyMember, Todo, WeeklyChoreAssignment
from app.points import book, lock_member
from app.schemas import IconName, TaskTitle
from app.today import family_now

router = APIRouter(prefix="/chores", tags=["chores"])

RoomName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
# Bis drei Jahre; seltener ist keine Hausarbeit mehr.
IntervalDays = Annotated[int, Field(ge=1, le=1095)]
# Stand beim Anlegen: gerade erledigt, mittendrin oder jetzt fällig.
StartState = Literal["fresh", "half", "due"]

# Der Assistent verteilt neue Aufgaben über ihren Abstand, damit nicht alles am selben Tag fällig
# wird: manche starten frisch, manche schon gelb, keine fällig.
_SPREAD = 0.618034
_SPREAD_MAX = 0.9

# Die faire Verteilung zählt die Erledigungen der letzten Tage, heute eingeschlossen.
SHARE_DAYS = 30


class RoomOut(BaseModel):
    id: int
    name: str
    icon: str


class ChoreOut(BaseModel):
    id: int
    room_id: int
    title: str
    icon: str
    interval_days: int
    active: bool
    estimated_minutes: int
    adult_xp: int
    assignment_mode: Literal["fixed", "rotate", "flexible"]
    fixed_member_id: int | None
    weekly_member_id: int | None = None
    # Letzte echte Erledigung; None = seit dem Anlegen noch nie.
    last_done: dt.date | None
    done_today: bool
    # Wer die letzte Erledigung übernommen hat, falls angegeben.
    done_by: int | None
    # Ab diesem Tag läuft die Uhr: die letzte Erledigung oder der Tag, den die Eltern festgelegt
    # haben.
    counted_from: dt.date
    due_date: dt.date
    # Tage bis zur Fälligkeit; 0 = heute, negativ = so viele Tage drüber.
    days_left: int
    # Verstrichener Anteil des Abstands; über 1 heißt überfällig.
    ratio: float
    # "ok", "soon" oder "due" (siehe app.chores).
    level: str


class ShareOut(BaseModel):
    member_id: int
    count: int


class ChoresOut(BaseModel):
    # Heute in der Zeitzone der Familie.
    date: dt.date
    rooms: list[RoomOut]
    chores: list[ChoreOut]
    # „Zu erledigen“: Offenes in der Reihenfolge des Eintragens, danach das heute Abgehakte.
    todos: list[TodoOut]
    # Faire Verteilung: wer in den letzten `share_days` Tagen wie oft etwas erledigt hat, im
    # Putzplan und von der Liste. Es zählt nur, wozu jemand „Wer war's?“ angetippt hat.
    share_days: int
    shares: list[ShareOut]


class RoomIn(BaseModel):
    name: RoomName
    icon: IconName


class ChoreIn(BaseModel):
    room_id: int
    title: TaskTitle
    icon: IconName
    interval_days: IntervalDays
    active: bool = True
    estimated_minutes: int = Field(default=15, ge=1, le=1440)
    adult_xp: int = Field(default=0, ge=0, le=1000)
    assignment_mode: Literal["fixed", "rotate", "flexible"] = "flexible"
    fixed_member_id: int | None = None
    # „Zuletzt erledigt“ von Hand, z. B. Fenster vor zehn Wochen geputzt; None = nicht anfassen.
    counted_from: dt.date | None = None


class ChoreCreateIn(ChoreIn):
    # Gilt nur ohne `counted_from`.
    state: StartState = "half"
    # „Kommt wieder“: Der Eintrag aus „Zu erledigen“ wird zu dieser Aufgabe und verlässt die Liste.
    todo_id: int | None = None


class DoneIn(BaseModel):
    # None = erledigt, ohne zu sagen von wem.
    member_id: int | None = None


class SetupChoreIn(BaseModel):
    title: TaskTitle
    icon: IconName
    interval_days: IntervalDays


class SetupRoomIn(BaseModel):
    name: RoomName
    icon: IconName
    chores: list[SetupChoreIn] = Field(max_length=100)


class SetupIn(BaseModel):
    rooms: list[SetupRoomIn] = Field(min_length=1, max_length=50)


class SetupOut(BaseModel):
    rooms: int
    chores: int


def _today(db: DbSession) -> dt.date:
    return family_now(get_family(db)).date()


def _get_room(db: DbSession, room_id: int) -> ChoreRoom:
    room = db.get(ChoreRoom, room_id)
    if room is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "chore.room_not_found")
    return room


def _validate_assignment(db: DbSession, body: ChoreIn) -> None:
    if body.assignment_mode == "fixed" and body.fixed_member_id is None:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.fixed_member_required")
    if body.fixed_member_id is not None:
        member = get_member(db, body.fixed_member_id)
        if member.role != "parent":
            raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.parent_required")


def _get_chore(db: DbSession, chore_id: int) -> Chore:
    chore = db.get(Chore, chore_id)
    if chore is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "chore.not_found")
    return chore


def _find_room(db: DbSession, name: str) -> ChoreRoom | None:
    return db.scalar(select(ChoreRoom).where(func.lower(ChoreRoom.name) == name.lower()))


def _room_out(room: ChoreRoom) -> RoomOut:
    return RoomOut(id=room.id, name=room.name, icon=room.icon)


def _counted_from(chore: Chore, last: ChoreCompletion | None) -> dt.date:
    """Die letzte Erledigung, außer die Eltern haben danach einen späteren Tag festgelegt."""
    return max(last.date, chore.anchor_date) if last else chore.anchor_date


def _chore_out(chore: Chore, last: ChoreCompletion | None, today: dt.date, weekly_member_id: int | None = None) -> ChoreOut:
    counted_from = _counted_from(chore, last)
    state = chore_state(counted_from, chore.interval_days, today)
    return ChoreOut(
        id=chore.id,
        room_id=chore.room_id,
        title=chore.title,
        icon=chore.icon,
        interval_days=chore.interval_days,
        active=chore.active,
        estimated_minutes=chore.estimated_minutes,
        adult_xp=chore.adult_xp,
        assignment_mode=chore.assignment_mode,
        fixed_member_id=chore.fixed_member_id,
        weekly_member_id=weekly_member_id,
        last_done=last.date if last else None,
        done_today=last is not None and last.date >= today,
        done_by=last.member_id if last else None,
        counted_from=counted_from,
        due_date=state.due_date,
        days_left=state.days_left,
        ratio=state.ratio,
        level=state.level,
    )


def _last_completions(db: DbSession, chore_ids: list[int]) -> dict[int, ChoreCompletion]:
    """Die jeweils jüngste Erledigung je Aufgabe."""
    latest = (
        select(ChoreCompletion.chore_id, func.max(ChoreCompletion.date).label("date"))
        .where(ChoreCompletion.chore_id.in_(chore_ids))
        .group_by(ChoreCompletion.chore_id)
        .subquery()
    )
    completions = db.scalars(
        select(ChoreCompletion).join(
            latest,
            and_(
                ChoreCompletion.chore_id == latest.c.chore_id,
                ChoreCompletion.date == latest.c.date,
            ),
        )
    )
    return {completion.chore_id: completion for completion in completions}


def _shares(db: DbSession, today: dt.date) -> list[ShareOut]:
    since = today - dt.timedelta(days=SHARE_DAYS - 1)
    counts = db.execute(
        select(ChoreCompletion.member_id, func.count())
        .where(
            ChoreCompletion.member_id.is_not(None),
            ChoreCompletion.date >= since,
            ChoreCompletion.date <= today,
        )
        .group_by(ChoreCompletion.member_id)
    )
    totals = todo_shares(db, since, today)
    for member_id, count in counts:
        totals[member_id] = totals.get(member_id, 0) + count
    return [ShareOut(member_id=member_id, count=totals[member_id]) for member_id in sorted(totals)]


def _reverse_chore_credits(db: DbSession, completions: list[ChoreCompletion], title: str) -> None:
    """Reverse booked XP before completions are removed by edits or deletion."""
    credits = [(completion, db.get(ChoreCredit, completion.id)) for completion in completions]
    for member_id in sorted({credit.member_id for _, credit in credits if credit is not None}):
        lock_member(db, member_id)
    for completion, credit in credits:
        if credit is not None:
            book(db, credit.member_id, -credit.amount, "chore_undone",
                 reason=title, task_date=completion.date)
            db.delete(credit)
    db.flush()


def _one_out(db: DbSession, chore: Chore) -> ChoreOut:
    today = _today(db)
    week_start = today - dt.timedelta(days=today.weekday())
    assignment = db.get(WeeklyChoreAssignment, (week_start, chore.id))
    return _chore_out(chore, _last_completions(db, [chore.id]).get(chore.id), today,
                      assignment.member_id if assignment else None)


def _anchor(state: StartState, interval_days: int, today: dt.date) -> dt.date:
    elapsed = {"fresh": 0, "half": interval_days // 2, "due": interval_days}[state]
    return today - dt.timedelta(days=elapsed)


def _check_counted_from(counted_from: dt.date | None, today: dt.date) -> None:
    if counted_from is not None and counted_from > today:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.counted_from_future")


def _commit_room(db: DbSession) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ApiError(status.HTTP_409_CONFLICT, "chore.room_duplicate") from error


@router.get("")
def list_chores(_: CurrentSession, db: DbSession) -> ChoresOut:
    """Alle Räume und Aufgaben mit ihrem Stand; das Display zeigt davon nur die aktiven."""
    today = _today(db)
    rooms = db.scalars(select(ChoreRoom).order_by(ChoreRoom.position, ChoreRoom.id))
    chores = list(db.scalars(select(Chore).order_by(Chore.id)))
    last = _last_completions(db, [chore.id for chore in chores])
    week_start = today - dt.timedelta(days=today.weekday())
    weekly = dict(db.execute(select(WeeklyChoreAssignment.chore_id, WeeklyChoreAssignment.member_id)
                             .where(WeeklyChoreAssignment.week_start == week_start)).all())
    return ChoresOut(
        date=today,
        rooms=[_room_out(room) for room in rooms],
        chores=[_chore_out(chore, last.get(chore.id), today, weekly.get(chore.id)) for chore in chores],
        todos=[todo_out(todo) for todo in visible_todos(db, today)],
        share_days=SHARE_DAYS,
        shares=_shares(db, today),
    )


class WeeklyAssignmentOut(BaseModel):
    chore_id: int
    member_id: int
    estimated_minutes: int
    adult_xp: int


class WeeklyPreviewOut(BaseModel):
    week_start: dt.date
    assignments: list[WeeklyAssignmentOut]


@router.get("/weekly-preview")
def weekly_preview(_: ParentSession, db: DbSession) -> WeeklyPreviewOut:
    """Read-only suggestion for chores due in the current calendar week.

    Fixed work counts toward each adult's load; recent completed minutes
    influence flexible assignments. Nothing is published or reassigned.
    """
    today = _today(db)
    week_start = today - dt.timedelta(days=today.weekday())
    week_end = week_start + dt.timedelta(days=6)
    adult_ids = list(db.scalars(
        select(FamilyMember.id).where(FamilyMember.role == "parent").order_by(FamilyMember.id)
    ))
    if not adult_ids:
        return WeeklyPreviewOut(week_start=week_start, assignments=[])
    chores = list(db.scalars(select(Chore).where(Chore.active.is_(True)).order_by(Chore.id)))
    last = _last_completions(db, [chore.id for chore in chores])
    due = [
        chore for chore in chores
        if chore_state(_counted_from(chore, last.get(chore.id)),
                       chore.interval_days, today).due_date <= week_end
    ]
    # A deleted adult can leave a fixed assignment without an owner (SET NULL).
    # Return a clear validation error rather than raising an unhandled ValueError.
    if any(chore.assignment_mode == "fixed" and chore.fixed_member_id not in adult_ids
           for chore in due):
        raise ApiError(status.HTTP_409_CONFLICT, "chore.fixed_member_required")
    since = today - dt.timedelta(days=29)
    history = db.execute(
        select(ChoreCompletion.member_id, Chore.estimated_minutes)
        .join(Chore, Chore.id == ChoreCompletion.chore_id)
        .where(ChoreCompletion.date >= since, ChoreCompletion.date <= today,
               ChoreCompletion.member_id.in_(adult_ids))
    )
    previous_minutes = {member_id: 0 for member_id in adult_ids}
    for member_id, minutes in history:
        previous_minutes[member_id] += minutes
    previous_assignees = {
        chore.id: last[chore.id].member_id
        for chore in due if chore.id in last and last[chore.id].member_id is not None
    }
    assignments = suggest_week(
        [HouseholdChore(chore.id, chore.estimated_minutes,
                        chore.assignment_mode, chore.fixed_member_id) for chore in due],
        adult_ids, previous_minutes, previous_assignees,
    )
    return WeeklyPreviewOut(
        week_start=week_start,
        assignments=[
            WeeklyAssignmentOut(chore_id=chore.id, member_id=assignments[chore.id],
                                estimated_minutes=chore.estimated_minutes,
                                adult_xp=chore.adult_xp)
            for chore in due
        ],
    )


class WeeklyPublishIn(BaseModel):
    assignments: list[WeeklyAssignmentOut] = Field(max_length=500)


@router.get("/weekly-confirmed")
def weekly_confirmed(_: ParentSession, db: DbSession) -> WeeklyPreviewOut:
    today = _today(db)
    week_start = today - dt.timedelta(days=today.weekday())
    rows = db.execute(
        select(WeeklyChoreAssignment, Chore)
        .join(Chore, Chore.id == WeeklyChoreAssignment.chore_id)
        .where(WeeklyChoreAssignment.week_start == week_start)
        .order_by(WeeklyChoreAssignment.chore_id)
    )
    return WeeklyPreviewOut(
        week_start=week_start,
        assignments=[
            WeeklyAssignmentOut(
                chore_id=assignment.chore_id, member_id=assignment.member_id,
                estimated_minutes=chore.estimated_minutes, adult_xp=chore.adult_xp,
            )
            for assignment, chore in rows
        ],
    )


@router.post("/weekly-confirmed")
def publish_weekly(body: WeeklyPublishIn, _: ParentSession, db: DbSession) -> WeeklyPreviewOut:
    """Explicit parent confirmation; atomically replaces this week's assignment plan."""
    preview = weekly_preview(_, db)
    expected = {entry.chore_id for entry in preview.assignments}
    submitted = {entry.chore_id for entry in body.assignments}
    if len(submitted) != len(body.assignments) or submitted != expected:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.weekly_invalid")
    adults = set(db.scalars(select(FamilyMember.id).where(FamilyMember.role == "parent")))
    chores = {chore.id: chore for chore in db.scalars(
        select(Chore).where(Chore.id.in_(expected))
    )}
    for entry in body.assignments:
        chore = chores[entry.chore_id]
        if entry.member_id not in adults or (
            chore.assignment_mode == "fixed" and chore.fixed_member_id != entry.member_id
        ):
            raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.weekly_invalid")
    db.execute(delete(WeeklyChoreAssignment).where(
        WeeklyChoreAssignment.week_start == preview.week_start
    ))
    db.add_all(
        WeeklyChoreAssignment(
            week_start=preview.week_start, chore_id=entry.chore_id,
            member_id=entry.member_id,
        )
        for entry in body.assignments
    )
    db.commit()
    return weekly_confirmed(_, db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_chore(body: ChoreCreateIn, _: ParentSession, db: DbSession) -> ChoreOut:
    _get_room(db, body.room_id)
    _validate_assignment(db, body)
    today = _today(db)
    _check_counted_from(body.counted_from, today)
    chore = Chore(
        room_id=body.room_id,
        title=body.title,
        icon=body.icon,
        interval_days=body.interval_days,
        active=body.active,
        estimated_minutes=body.estimated_minutes,
        adult_xp=body.adult_xp,
        assignment_mode=body.assignment_mode,
        fixed_member_id=body.fixed_member_id if body.assignment_mode == "fixed" else None,
        anchor_date=body.counted_from or _anchor(body.state, body.interval_days, today),
    )
    db.add(chore)
    todo = db.get(Todo, body.todo_id) if body.todo_id is not None else None
    # Schon Abgehaktes bleibt bis zum Tagesende stehen und zählt weiter für die faire Verteilung.
    if todo is not None and todo.done_date is None:
        db.delete(todo)
    db.commit()
    return _one_out(db, chore)


# Vor /{chore_id}, sonst hielte FastAPI „rooms“ und „setup“ für eine ID.
@router.post("/rooms", status_code=status.HTTP_201_CREATED)
def create_room(body: RoomIn, _: ParentSession, db: DbSession) -> RoomOut:
    if _find_room(db, body.name) is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "chore.room_duplicate")
    position = db.scalar(select(func.coalesce(func.max(ChoreRoom.position), -1))) + 1
    room = ChoreRoom(name=body.name, icon=body.icon, position=position)
    db.add(room)
    _commit_room(db)
    return _room_out(room)


@router.put("/rooms/{room_id}")
def update_room(room_id: int, body: RoomIn, _: ParentSession, db: DbSession) -> RoomOut:
    room = _get_room(db, room_id)
    other = _find_room(db, body.name)
    if other is not None and other.id != room.id:
        raise ApiError(status.HTTP_409_CONFLICT, "chore.room_duplicate")
    room.name, room.icon = body.name, body.icon
    _commit_room(db)
    return _room_out(room)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, _: ParentSession, db: DbSession) -> None:
    """Löscht einen Raum mitsamt seinen Aufgaben."""
    room = _get_room(db, room_id)
    chores = list(db.scalars(select(Chore).where(Chore.room_id == room.id)))
    for chore in chores:
        completions = list(db.scalars(select(ChoreCompletion).where(
            ChoreCompletion.chore_id == chore.id,
        ).with_for_update()))
        _reverse_chore_credits(db, completions, chore.title)
        for completion in completions:
            db.delete(completion)
    db.flush()
    db.delete(room)
    db.commit()


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup_chores(body: SetupIn, _: ParentSession, db: DbSession) -> SetupOut:
    """Übernimmt die Vorschläge des Einrichtungs-Assistenten.

    Räume mit gleichem Namen werden weiterverwendet, dort schon vorhandene Aufgaben übersprungen;
    der Assistent lässt sich also gefahrlos ein zweites Mal ausführen.
    """
    today = _today(db)
    position = db.scalar(select(func.coalesce(func.max(ChoreRoom.position), -1))) + 1
    created_rooms = created_chores = 0
    for room_in in body.rooms:
        room = _find_room(db, room_in.name)
        if room is None:
            room = ChoreRoom(name=room_in.name, icon=room_in.icon, position=position)
            db.add(room)
            db.flush()
            position += 1
            created_rooms += 1
        existing = {
            title.lower()
            for title in db.scalars(select(Chore.title).where(Chore.room_id == room.id))
        }
        for chore_in in room_in.chores:
            if chore_in.title.lower() in existing:
                continue
            existing.add(chore_in.title.lower())
            elapsed = int((created_chores * _SPREAD % 1) * _SPREAD_MAX * chore_in.interval_days)
            db.add(
                Chore(
                    room_id=room.id,
                    title=chore_in.title,
                    icon=chore_in.icon,
                    interval_days=chore_in.interval_days,
                    anchor_date=today - dt.timedelta(days=elapsed),
                )
            )
            created_chores += 1
    _commit_room(db)
    return SetupOut(rooms=created_rooms, chores=created_chores)


@router.put("/{chore_id}")
def update_chore(chore_id: int, body: ChoreIn, _: ParentSession, db: DbSession) -> ChoreOut:
    """Ändert eine Aufgabe; ein neuer Abstand zählt ab der letzten Erledigung.

    Mit `counted_from` legen die Eltern fest, wann sie zuletzt erledigt wurde. Liegt der Tag vor
    schon abgehakten Erledigungen, werden diese gelöscht: Sonst zählte weiter die jüngste davon.
    """
    chore = _get_chore(db, chore_id)
    _get_room(db, body.room_id)
    # Validate the effective values, including metadata omitted by legacy clients.
    fields = body.model_fields_set
    effective_mode = body.assignment_mode if "assignment_mode" in fields else chore.assignment_mode
    effective_fixed = (
        body.fixed_member_id if "fixed_member_id" in fields else chore.fixed_member_id
    ) if effective_mode == "fixed" else None
    _validate_assignment(db, body.model_copy(update={
        "assignment_mode": effective_mode, "fixed_member_id": effective_fixed,
    }))
    last = _last_completions(db, [chore.id]).get(chore.id)
    # Nur ein geänderter Tag greift ein, damit ein unverändert mitgeschickter nichts löscht.
    if body.counted_from is not None and body.counted_from != _counted_from(chore, last):
        _check_counted_from(body.counted_from, _today(db))
        chore.anchor_date = body.counted_from
        removed = list(db.scalars(select(ChoreCompletion).where(
            ChoreCompletion.chore_id == chore.id,
            ChoreCompletion.date > body.counted_from,
        ).with_for_update()))
        _reverse_chore_credits(db, removed, chore.title)
        for completion in removed:
            db.delete(completion)
    chore.room_id, chore.title, chore.icon = body.room_id, body.title, body.icon
    chore.interval_days, chore.active = body.interval_days, body.active
    # Older clients do not send adult fields. Preserve existing settings in that case.
    if "estimated_minutes" in fields:
        chore.estimated_minutes = body.estimated_minutes
    if "adult_xp" in fields:
        chore.adult_xp = body.adult_xp
    chore.assignment_mode = effective_mode
    chore.fixed_member_id = effective_fixed
    db.commit()
    return _one_out(db, chore)


@router.delete("/{chore_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chore(chore_id: int, _: ParentSession, db: DbSession) -> None:
    chore = _get_chore(db, chore_id)
    completions = list(db.scalars(select(ChoreCompletion).where(
        ChoreCompletion.chore_id == chore.id,
    ).with_for_update()))
    _reverse_chore_credits(db, completions, chore.title)
    for completion in completions:
        db.delete(completion)
    db.flush()
    db.delete(chore)
    db.commit()


@router.put("/{chore_id}/done")
def mark_done(chore_id: int, body: DoneIn, _: CurrentSession, db: DbSession) -> ChoreOut:
    """Heute erledigt. Ein zweiter Aufruf am selben Tag trägt nur nach, wer es war."""
    chore = _get_chore(db, chore_id)
    if body.member_id is not None:
        get_member(db, body.member_id)
    today = _today(db)
    query = select(ChoreCompletion).where(
        ChoreCompletion.chore_id == chore.id, ChoreCompletion.date == today
    )
    completion = db.scalar(query)
    if completion is None:
        db.add(ChoreCompletion(chore_id=chore.id, date=today, member_id=body.member_id))
        try:
            db.commit()
        except IntegrityError:
            # Doppel-Tipp oder gleichzeitig auf einem anderen Gerät erledigt.
            db.rollback()
            completion = db.scalar(query)
    if completion is not None:
        credit = db.get(ChoreCredit, completion.id)
        if credit is not None and body.member_id != credit.member_id:
            raise ApiError(status.HTTP_409_CONFLICT, "chore.credit_requires_parent")
        completion.member_id = body.member_id
        db.commit()
    return _one_out(db, chore)


@router.post("/{chore_id}/credit")
def approve_chore_credit(chore_id: int, body: DoneIn, _: ParentSession, db: DbSession) -> ChoreOut:
    """Parent-approved XP for today's completed chore; repeated approval is idempotent."""
    chore = _get_chore(db, chore_id)
    if body.member_id is None:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.parent_required")
    member = get_member(db, body.member_id)
    if member.role != "parent":
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "chore.parent_required")
    today = _today(db)
    completion = db.scalar(
        select(ChoreCompletion)
        .where(ChoreCompletion.chore_id == chore.id, ChoreCompletion.date == today)
        .with_for_update()
    )
    if completion is None:
        raise ApiError(status.HTTP_409_CONFLICT, "chore.not_completed")
    old = db.get(ChoreCredit, completion.id)
    amount = chore.adult_xp
    if old is not None and old.member_id == member.id and old.amount == amount:
        return _one_out(db, chore)
    # Serialize balance-affecting changes; lock in stable order.
    for member_id in sorted({member.id, old.member_id} if old else {member.id}):
        lock_member(db, member_id)
    if old is not None:
        book(db, old.member_id, -old.amount, "chore_undone",
             reason=chore.title, task_date=today)
        db.delete(old)
        db.flush()
    if amount > 0:
        book(db, member.id, amount, "chore_completed",
             reason=chore.title, task_date=today)
        db.add(ChoreCredit(completion_id=completion.id, member_id=member.id, amount=amount))
    completion.member_id = member.id
    db.commit()
    return _one_out(db, chore)


@router.delete("/{chore_id}/done")
def undo_done(chore_id: int, auth_session: CurrentSession, db: DbSession) -> ChoreOut:
    """Nimmt die heutige Erledigung zurück; frühere bleiben stehen."""
    chore = _get_chore(db, chore_id)
    completion = db.scalar(
        select(ChoreCompletion).where(
            ChoreCompletion.chore_id == chore.id, ChoreCompletion.date == _today(db)
        ).with_for_update()
    )
    if completion is not None:
        credit = db.get(ChoreCredit, completion.id)
        if credit is not None:
            # Undoing parent-approved XP requires an unlocked parent session.
            if not is_parent_unlocked(auth_session, get_family(db)):
                raise ApiError(status.HTTP_403_FORBIDDEN, "parent.locked")
            lock_member(db, credit.member_id)
            book(db, credit.member_id, -credit.amount, "chore_undone",
                 reason=chore.title, task_date=completion.date)
            db.delete(credit)
        db.delete(completion)
        db.commit()
    return _one_out(db, chore)
