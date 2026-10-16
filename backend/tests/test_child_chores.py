from fastapi.testclient import TestClient

from tests.conftest import csrf
from tests.test_adult_chore_credits import parent_member, total
from tests.test_chores import add_chore, add_room
from tests.test_personal_access import add_person


def test_shared_household_task_is_scoped_and_requires_child_approval(client, parent, now):
    child_id, credentials = add_person(client, parent, "Lena", "purple")
    other_id, _ = add_person(client, parent, "Tom", "green")
    adult = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    item = add_chore(
        client,
        parent,
        room["id"],
        child_enabled=True,
        child_member_ids=[child_id],
        child_xp=4,
        adult_xp=10,
        repeatable=True,
    )
    private = add_chore(client, parent, room["id"], title="Parents only")
    add_chore(
        client,
        parent,
        room["id"],
        title="Other child",
        child_enabled=True,
        child_member_ids=[other_id],
    )
    add_chore(
        client,
        parent,
        room["id"],
        title="Assigned parent",
        child_enabled=True,
        child_member_ids=[child_id],
        assignment_mode="fixed",
        fixed_member_id=adult,
    )
    child = TestClient(client.app)
    try:
        me = child.post("/api/auth/login", json=credentials).json()
        assert [row["id"] for row in child.get("/api/chores/mine").json()] == [item["id"]]
        assert child.get("/api/chores").status_code == 403
        path = f"/api/chores/mine/{item['id']}/done"
        body = {"request_key": "d" * 32}
        assert child.put(path, json=body, headers=csrf(me)).status_code == 200
        assert child.put(path, json=body, headers=csrf(me)).status_code == 200
        assert total(child_id) == 0
        approvals = client.get("/api/approvals").json()
        assert len(approvals) == 1
        approval = approvals[0]
        assert approval["source"] == "chore"
        assert approval["points"] == 4
        assert client.get("/api/today").json()["pending_approvals"] == 1
        assert (
            child.post(f"/api/chore-approvals/{approval['id']}", headers=csrf(me)).status_code
            == 403
        )
        assert (
            child.put(
                f"/api/chores/mine/{private['id']}/done", json=body, headers=csrf(me)
            ).status_code
            == 403
        )
        assert (
            child.put(
                path, json={"request_key": "e" * 32, "member_id": other_id}, headers=csrf(me)
            ).status_code
            == 403
        )
        assert (
            client.post(f"/api/chore-approvals/{approval['id']}", headers=csrf(parent)).status_code
            == 204
        )
        assert (
            client.post(f"/api/chore-approvals/{approval['id']}", headers=csrf(parent)).status_code
            == 204
        )
        assert total(child_id) == 4
        assert client.get("/api/today").json()["pending_approvals"] == 0
        assert child.put(path, json={"request_key": "f" * 32}, headers=csrf(me)).status_code == 200
        second = client.get("/api/approvals").json()[0]
        assert (
            client.delete(f"/api/chore-approvals/{second['id']}", headers=csrf(parent)).status_code
            == 204
        )
        assert total(child_id) == 4
        assert (
            client.put(
                f"/api/chores/{item['id']}/done",
                json={"request_key": "9" * 32, "member_id": adult},
                headers=csrf(parent),
            ).status_code
            == 200
        )
        assert total(adult) == 10
    finally:
        child.close()


def test_weekly_assignment_respects_child_eligibility():
    from app.household_assignment import HouseholdChore, suggest_week

    chores = [
        HouseholdChore(1, 10, eligible_member_ids=(10,)),
        HouseholdChore(2, 10, eligible_member_ids=(10, 20)),
    ]
    result = suggest_week(chores, [10, 20])
    assert result == {1: 10, 2: 20}
