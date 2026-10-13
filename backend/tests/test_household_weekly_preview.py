"""Read-only weekly assignment preview integration tests."""
from tests.conftest import csrf
from tests.test_chores import add_chore, add_room
from tests.test_adult_chore_credits import parent_member


def test_weekly_preview_keeps_fixed_shopping_and_balances_work(client, parent, now):
    flo = parent_member(client, parent, "Flo", color="blue")
    viola = parent_member(client, parent, "Viola", color="green")
    room = add_room(client, parent)
    shopping = add_chore(
        client, parent, room["id"], title="Wocheneinkauf", interval_days=7,
        estimated_minutes=90, adult_xp=15, assignment_mode="fixed", fixed_member_id=flo,
        state="due",
    )
    cleaning = add_chore(
        client, parent, room["id"], title="Bad putzen", interval_days=7,
        estimated_minutes=30, adult_xp=15, state="due",
    )
    response = client.get("/api/chores/weekly-preview")
    assert response.status_code == 200, response.text
    assignments = {item["chore_id"]: item for item in response.json()["assignments"]}
    assert assignments[shopping["id"]]["member_id"] == flo
    assert assignments[shopping["id"]]["adult_xp"] == 15
    assert assignments[cleaning["id"]]["member_id"] == viola
    # Preview must not mark tasks done or persist assignments.
    chores = client.get("/api/chores").json()["chores"]
    assert all(not chore["done_today"] for chore in chores)


def test_weekly_preview_requires_parent_unlock(client, parent, now):
    from app.db import SessionLocal
    from app.models import AuthSession
    from sqlalchemy import update
    with SessionLocal() as db:
        db.execute(update(AuthSession).values(parent_unlocked_until=None))
        db.commit()
    response = client.get("/api/chores/weekly-preview")
    assert response.status_code == 403, response.text


def test_confirmed_week_is_persisted_and_fixed_work_cannot_move(client, parent, now):
    flo = parent_member(client, parent, "Flo", color="blue")
    viola = parent_member(client, parent, "Viola", color="green")
    room = add_room(client, parent)
    shopping = add_chore(
        client, parent, room["id"], title="Wocheneinkauf", interval_days=7,
        estimated_minutes=90, adult_xp=15, assignment_mode="fixed", fixed_member_id=flo,
        state="due",
    )
    cleaning = add_chore(
        client, parent, room["id"], title="Bad putzen", interval_days=7,
        estimated_minutes=30, state="due",
    )
    preview = client.get("/api/chores/weekly-preview").json()
    assignments = preview["assignments"]
    changed = [{**entry, "member_id": viola} if entry["chore_id"] == shopping["id"] else entry
               for entry in assignments]
    rejected = client.post(
        "/api/chores/weekly-confirmed", json={"assignments": changed}, headers=csrf(parent),
    )
    assert rejected.status_code == 422, rejected.text
    assert client.get("/api/chores/weekly-confirmed").json()["assignments"] == []

    approved = client.post(
        "/api/chores/weekly-confirmed", json={"assignments": assignments}, headers=csrf(parent),
    )
    assert approved.status_code == 200, approved.text
    saved = client.get("/api/chores/weekly-confirmed").json()
    assert saved["assignments"] == assignments
    visible = {item["id"]: item for item in client.get("/api/chores").json()["chores"]}
    assert visible[shopping["id"]]["weekly_member_id"] == flo
    assert visible[cleaning["id"]]["weekly_member_id"] == next(
        entry["member_id"] for entry in assignments if entry["chore_id"] == cleaning["id"]
    )
    assert {entry["chore_id"] for entry in saved["assignments"]} == {
        shopping["id"], cleaning["id"],
    }
    again = client.post(
        "/api/chores/weekly-confirmed", json={"assignments": assignments}, headers=csrf(parent),
    )
    assert again.status_code == 200, again.text
    assert len(again.json()["assignments"]) == 2


def test_confirmed_week_rejects_incomplete_plan(client, parent, now):
    parent_member(client, parent, "Flo", color="blue")
    room = add_room(client, parent)
    add_chore(client, parent, room["id"], title="Bad putzen", state="due")
    response = client.post(
        "/api/chores/weekly-confirmed", json={"assignments": []}, headers=csrf(parent),
    )
    assert response.status_code == 422, response.text


def test_weekly_preview_reports_deleted_fixed_adult_as_conflict(client, parent, now):
    flo = parent_member(client, parent, "Flo", color="blue")
    room = add_room(client, parent)
    add_chore(
        client, parent, room["id"], title="Wocheneinkauf",
        assignment_mode="fixed", fixed_member_id=flo, state="due",
    )
    from app.db import SessionLocal
    from app.models import FamilyMember
    with SessionLocal() as db:
        member = db.get(FamilyMember, flo)
        db.delete(member)
        db.commit()
    response = client.get("/api/chores/weekly-preview")
    assert response.status_code == 409, response.text
