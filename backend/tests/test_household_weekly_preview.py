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
