"""Tests for adult XP approval on completed household chores."""

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import PointTransaction
from tests.conftest import csrf
from tests.test_chores import add_chore, add_room, done


def parent_member(client, parent, name, color="blue"):
    response = client.post(
        "/api/members",
        json={
            "name": name,
            "role": "parent",
            "color": color,
        },
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def total(member_id):
    with SessionLocal() as db:
        return db.scalar(
            select(func.coalesce(func.sum(PointTransaction.amount), 0)).where(
                PointTransaction.member_id == member_id,
            )
        )


def approve(client, parent, chore_id, member_id):
    return client.post(
        f"/api/chores/{chore_id}/credit", json={"member_id": member_id}, headers=csrf(parent)
    )


def test_approval_requires_completion(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    assert approve(client, parent, item["id"], flo).status_code == 409
    assert done(client, parent, item["id"], flo).status_code == 200
    assert total(flo) == 15  # credited immediately, without a separate approval
    assert approve(client, parent, item["id"], flo).status_code == 200
    assert total(flo) == 15


def test_repeated_approval_and_undo(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    done(client, parent, item["id"], flo)
    for _ in range(3):
        assert approve(client, parent, item["id"], flo).status_code == 200
    assert total(flo) == 15
    assert client.delete(f"/api/chores/{item['id']}/done", headers=csrf(parent)).status_code == 200
    assert total(flo) == 0


def test_parent_can_correct_who_completed_the_chore(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    viola = parent_member(client, parent, "Viola", color="green")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    done(client, parent, item["id"], flo)
    approve(client, parent, item["id"], flo)
    assert done(client, parent, item["id"], viola).status_code == 200
    assert approve(client, parent, item["id"], viola).status_code == 200
    assert (total(flo), total(viola)) == (0, 15)


def test_child_cannot_receive_adult_xp(client, parent, now):
    from tests.test_tasks import add_member

    child_id = add_member(client, parent)
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    assert done(client, parent, item["id"], child_id).status_code == 200
    assert approve(client, parent, item["id"], child_id).status_code == 422
    assert total(child_id) == 0


def test_legacy_update_preserves_adult_settings(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(
        client,
        parent,
        room["id"],
        adult_xp=15,
        estimated_minutes=60,
        assignment_mode="fixed",
        fixed_member_id=flo,
    )
    response = client.put(
        f"/api/chores/{item['id']}",
        json={
            "room_id": room["id"],
            "title": "Wocheneinkauf",
            "icon": "fluent-emoji-flat:toilet",
            "interval_days": 7,
            "active": True,
        },
        headers=csrf(parent),
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["adult_xp"] == 15
    assert changed["estimated_minutes"] == 60
    assert changed["assignment_mode"] == "fixed"
    assert changed["fixed_member_id"] == flo


def test_credited_chore_undo_requires_parent_role(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    done(client, parent, item["id"], flo)
    assert approve(client, parent, item["id"], flo).status_code == 200

    account = client.post(
        "/api/auth/accounts",
        json={
            "email": "child-credits@example.org",
            "password": "test-password-456",
            "role": "child",
        },
        headers=csrf(parent),
    )
    assert account.status_code == 201, account.text
    assert client.post("/api/auth/logout", headers=csrf(parent)).status_code == 204
    login = client.post(
        "/api/auth/login",
        json={"email": "child-credits@example.org", "password": "test-password-456"},
    )
    assert login.status_code == 200, login.text
    blocked = client.delete(f"/api/chores/{item['id']}/done", headers=csrf(login.json()))
    assert blocked.status_code == 403, blocked.text
    assert total(flo) == 15


def test_uncredited_chore_can_be_undone_without_parent_unlock(client, parent, now):
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    assert done(client, parent, item["id"]).status_code == 200

    from sqlalchemy import update

    from app.models import AuthSession

    with SessionLocal() as db:
        db.execute(update(AuthSession).values(parent_unlocked_until=None))
        db.commit()

    response = client.delete(f"/api/chores/{item['id']}/done", headers=csrf(parent))
    assert response.status_code == 200, response.text
    assert response.json()["done_today"] is False


def test_legacy_update_validates_fixed_member_changes(client, parent, now):
    flo = parent_member(client, parent, "Flo", color="blue")
    from tests.test_tasks import add_member

    child = add_member(client, parent, name="Tim", color="purple")
    room = add_room(client, parent)
    item = add_chore(
        client,
        parent,
        room["id"],
        assignment_mode="fixed",
        fixed_member_id=flo,
    )
    original = client.get("/api/chores").json()["chores"][0]
    payload = {
        "room_id": room["id"],
        "title": original["title"],
        "icon": original["icon"],
        "interval_days": original["interval_days"],
        "active": True,
        "fixed_member_id": child,
    }
    response = client.put(f"/api/chores/{item['id']}", json=payload, headers=csrf(parent))
    assert response.status_code == 422, response.text
    saved = client.get("/api/chores").json()["chores"][0]
    assert saved["fixed_member_id"] == flo


def test_repeat_executions_credit_independently_and_undo_exact_execution(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    viola = parent_member(client, parent, "Viola", color="green")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=10, repeatable=True)
    path = f"/api/chores/{item['id']}/done"
    first_body = {"member_id": flo, "request_key": "a" * 32}
    first = client.put(path, json=first_body, headers=csrf(parent)).json()
    assert first["completion_count_today"] == 1
    assert total(flo) == 10
    assert client.put(path, json=first_body, headers=csrf(parent)).status_code == 200
    assert total(flo) == 10
    second = client.put(
        path, json={"member_id": viola, "request_key": "b" * 32}, headers=csrf(parent)
    ).json()
    assert second["completion_count_today"] == 2
    assert (total(flo), total(viola)) == (10, 10)
    # Retrying the initial unattributed request cannot remove the selected person or XP.
    client.put(path, json={"request_key": "b" * 32}, headers=csrf(parent))
    assert total(viola) == 10
    undo_path = f"{path}?completion_id={second['last_completion_id']}"
    undone = client.delete(undo_path, headers=csrf(parent)).json()
    assert undone["completion_count_today"] == 1
    assert undone["last_completion_id"] == first["last_completion_id"]
    assert (total(flo), total(viola)) == (10, 0)
    assert client.delete(undo_path, headers=csrf(parent)).status_code == 200
    assert total(flo) == 10


def test_concurrent_household_request_is_credited_once(client, parent, now):
    from concurrent.futures import ThreadPoolExecutor

    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=10, repeatable=True)

    def attempt(_):
        return client.put(
            f"/api/chores/{item['id']}/done",
            json={"member_id": flo, "request_key": "c" * 32},
            headers=csrf(parent),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(attempt, range(4)))
    assert [response.status_code for response in responses] == [200] * 4
    assert total(flo) == 10
