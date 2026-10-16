from fastapi.testclient import TestClient

from tests.conftest import csrf
from tests.test_adult_chore_credits import parent_member, total
from tests.test_approvals import approvals, room_task
from tests.test_chores import add_chore, add_room
from tests.test_personal_access import add_person
from tests.test_today import complete


def test_praise_is_idempotent_and_independent_of_stars(client, parent, lena, now):
    path = f"/api/members/{lena}/praise"
    payload = {"reason": "Great help", "request_key": "a" * 32}
    first = client.post(path, json=payload, headers=csrf(parent))
    assert first.status_code == 201, first.text
    assert client.post(path, json=payload, headers=csrf(parent)).json() == first.json()
    progress = client.get(f"/api/members/{lena}/progress").json()
    assert progress["praise_count"] == 1
    assert progress["latest_praise_reason"] == "Great help"
    assert progress["earned_xp"] == 0
    assert total(lena) == 0
    assert (
        client.post(path, json={**payload, "reason": "Changed"}, headers=csrf(parent)).status_code
        == 409
    )
    assert (
        client.post(path, json={**payload, "reason": "   "}, headers=csrf(parent)).status_code
        == 422
    )


def test_approval_can_grant_one_heart_in_same_transaction(client, parent, lena, now):
    task = room_task(client, parent, [lena])
    complete(client, parent, task, lena)
    [pending] = approvals(client)
    path = f"/api/approvals/{pending['id']}?praise=true"
    assert client.post(path, headers=csrf(parent)).status_code == 204
    assert client.post(path, headers=csrf(parent)).status_code == 404
    assert client.get(f"/api/members/{lena}/progress").json()["praise_count"] == 1
    assert total(lena) == 5
    assert (
        client.post(
            f"/api/members/{lena}/points",
            json={"amount": -2, "reason": "Correction"},
            headers=csrf(parent),
        ).status_code
        == 201
    )
    progress = client.get(f"/api/members/{lena}/progress").json()
    assert progress["praise_count"] == 1
    assert progress["earned_xp"] == 5
    assert total(lena) == 3
    assert progress["latest_deduction_amount"] == 2
    assert progress["latest_deduction_reason"] == "Correction"
    assert progress["latest_deduction_id"] > 0


def test_children_cannot_praise_or_read_other_child_progress(client, parent, now):
    one, credentials = add_person(client, parent, "Lena", "purple")
    two, _ = add_person(client, parent, "Tom", "green")
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert (
            child.post(
                f"/api/members/{one}/praise",
                json={"reason": "Self", "request_key": "b" * 32},
                headers=csrf(me),
            ).status_code
            == 403
        )
        assert child.get(f"/api/members/{two}/progress").status_code == 403


def test_fixed_household_can_only_be_completed_for_assignee(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    viola = parent_member(client, parent, "Viola", color="purple")
    room = add_room(client, parent)
    chore = add_chore(
        client, parent, room["id"], assignment_mode="fixed", fixed_member_id=flo, adult_xp=10
    )
    path = f"/api/chores/{chore['id']}/done"
    for person in (None, viola):
        response = client.put(path, json={"member_id": person}, headers=csrf(parent))
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "chore.fixed_assignee_only"
    assert total(flo) == total(viola) == 0
    assert client.put(path, json={"member_id": flo}, headers=csrf(parent)).status_code == 200
    assert total(flo) == 10
    correction = client.post(
        f"/api/chores/{chore['id']}/credit", json={"member_id": viola}, headers=csrf(parent)
    )
    assert correction.status_code == 409
    assert total(flo) == 10 and total(viola) == 0


def test_household_approval_with_praise_is_atomic_and_not_repeated(client, parent, now):
    child_id, credentials = add_person(client, parent, "Lena", "purple")
    room = add_room(client, parent)
    chore = add_chore(
        client, parent, room["id"], child_enabled=True, child_member_ids=[child_id], child_xp=3
    )
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        response = child.put(
            f"/api/chores/mine/{chore['id']}/done", json={"request_key": "c" * 32}, headers=csrf(me)
        )
        assert response.status_code == 200, response.text
    [pending] = approvals(client)
    path = f"/api/chore-approvals/{pending['id']}?praise=true"
    for _ in range(2):
        assert client.post(path, headers=csrf(parent)).status_code == 204
    assert total(child_id) == 3
    progress = client.get(f"/api/members/{child_id}/progress").json()
    assert progress["praise_count"] == 1
    history = client.get(f"/api/members/{child_id}/praise").json()["praises"]
    assert len(history) == 1
    assert history[0]["reason"] == chore["title"]
