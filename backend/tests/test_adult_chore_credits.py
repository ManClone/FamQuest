"""Tests for adult XP approval on completed household chores."""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import PointTransaction
from tests.conftest import csrf
from tests.test_chores import add_chore, add_room, done


def parent_member(client, parent, name):
    response = client.post("/api/members", json={
        "name": name, "role": "parent", "color": "blue",
    }, headers=csrf(parent))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def total(member_id):
    with SessionLocal() as db:
        return db.scalar(select(func.coalesce(func.sum(PointTransaction.amount), 0)).where(
            PointTransaction.member_id == member_id,
        ))


def approve(client, parent, chore_id, member_id):
    return client.post(f"/api/chores/{chore_id}/credit",
                       json={"member_id": member_id}, headers=csrf(parent))


def test_approval_requires_completion(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    assert approve(client, parent, item["id"], flo).status_code == 409
    assert done(client, parent, item["id"], flo).status_code == 200
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


def test_transfer_requires_approval(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    viola = parent_member(client, parent, "Viola")
    room = add_room(client, parent)
    item = add_chore(client, parent, room["id"], adult_xp=15)
    done(client, parent, item["id"], flo)
    approve(client, parent, item["id"], flo)
    assert done(client, parent, item["id"], viola).status_code == 409
    assert approve(client, parent, item["id"], viola).status_code == 200
    assert (total(flo), total(viola)) == (0, 15)
