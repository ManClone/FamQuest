from fastapi.testclient import TestClient

from tests.conftest import csrf
from tests.test_today import add_task, completion_url


def add_person(client, parent, name, color):
    credentials = {"email": f"{name.lower()}@example.org", "password": "test-password-123"}
    response = client.post(
        "/api/members",
        json={"name": name, "role": "child", "color": color, "login": credentials},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], credentials


def test_children_only_read_and_complete_their_own_tasks(client, parent, now):
    one, credentials = add_person(client, parent, "Lena", "purple")
    two, _ = add_person(client, parent, "Tom", "green")
    own_task = add_task(client, parent, [one])
    other_task = add_task(client, parent, [two])
    child = TestClient(client.app)
    try:
        me = child.post("/api/auth/login", json=credentials).json()
        assert me["member_id"] == one
        assert [m["id"] for m in child.get("/api/members").json()] == [one]
        assert [t["id"] for t in child.get("/api/tasks").json()] == [own_task]
        today = child.get("/api/today").json()
        assert [t["id"] for t in today["tasks"]] == [own_task]
        assert [p["member_id"] for p in today["points"]] == [one]
        assert child.put(completion_url(other_task, two), headers=csrf(me)).status_code == 403
        assert child.put(completion_url(own_task, one), headers=csrf(me)).status_code == 204
        assert child.get(f"/api/members/{two}/points").status_code == 403
        assert child.get(f"/api/members/{one}/points").status_code == 200
        for path in ("/api/chores", "/api/approvals", "/api/auth/accounts"):
            assert child.get(path).status_code == 403
        assert (
            child.post("/api/todos", json={"title": "No access"}, headers=csrf(me)).status_code
            == 403
        )
        week = child.get("/api/tasks/week").json()
        assert {t["id"] for t in week["tasks"]} == {own_task}
        assert all(e["member_id"] == one for d in week["days"] for e in d["entries"])
    finally:
        child.close()


def test_profile_updates_cannot_change_roles_or_other_members(client, parent):
    member_id, credentials = add_person(client, parent, "Lena", "purple")
    child = TestClient(client.app)
    other_session = TestClient(client.app)
    try:
        me = child.post("/api/auth/login", json=credentials).json()
        other_session.post("/api/auth/login", json=credentials)
        assert child.get("/api/profile").json()["member"]["id"] == member_id
        assert (
            child.put(
                "/api/profile", json={"name": "Leni", "role": "parent"}, headers=csrf(me)
            ).status_code
            == 422
        )
        assert child.put("/api/profile", json={"name": "Leni"}, headers=csrf(me)).status_code == 200
        body = {"current_password": "wrong", "new_password": "new-password-456"}
        assert child.put("/api/profile/password", json=body, headers=csrf(me)).status_code == 403
        body["current_password"] = credentials["password"]
        assert child.put("/api/profile/password", json=body, headers=csrf(me)).status_code == 204
        assert child.get("/api/auth/me").status_code == 200
        assert other_session.get("/api/auth/me").status_code == 401
        assert child.get("/api/auth/me").json()["user"]["role"] == "child"
    finally:
        child.close()
        other_session.close()


def test_unlinked_child_is_never_shown_other_children(client, parent, lena, now):
    add_task(client, parent, [lena])
    credentials = {"email": "unlinked@example.org", "password": "test-password-123"}
    client.post("/api/auth/accounts", json={**credentials, "role": "child"}, headers=csrf(parent))
    child = TestClient(client.app)
    try:
        assert child.post("/api/auth/login", json=credentials).json()["member_id"] is None
        assert child.get("/api/members").json() == []
        assert child.get("/api/today").json()["tasks"] == []
        assert child.get("/api/rewards").json() == []
        assert child.get("/api/tasks/week").json()["tasks"] == []
    finally:
        child.close()


def test_child_progress_and_redemption_history_are_personal_and_purchases_keep_levels(
    client, parent, now
):
    from tests.test_rewards import add_reward, redeem
    from tests.test_today import complete

    one, credentials = add_person(client, parent, "Lena", "purple")
    two, _ = add_person(client, parent, "Tom", "green")
    for member in (one, two):
        task = add_task(client, parent, [member], points=100)
        assert complete(client, parent, task, member).status_code == 204
    own_reward = add_reward(client, parent, one, cost=10)
    other_reward = add_reward(client, parent, two, cost=10)
    assert redeem(client, parent, other_reward).status_code == 201
    child = TestClient(client.app)
    try:
        me = child.post("/api/auth/login", json=credentials).json()
        assert child.get(f"/api/members/{two}/progress").status_code == 403
        expected = {
            "praise_count": 0,
            "latest_praise_id": 0,
            "latest_praise_reason": None,
            "earned_xp": 100,
            "level": 2,
            "level_progress": 0,
            "level_size": 100,
            "remaining_xp": 100,
        }
        assert child.get(f"/api/members/{one}/progress").json() == expected
        assert child.get("/api/redemptions").json()["redemptions"] == []
        assert child.get(f"/api/redemptions?member_id={two}").status_code == 403
        for _ in range(2):
            assert redeem(child, me, own_reward).status_code == 201
        first = child.get("/api/redemptions?limit=1").json()
        assert first["has_more"] is True
        assert first["redemptions"][0]["member_id"] == one
        cursor = first["redemptions"][0]["id"]
        second = child.get(f"/api/redemptions?limit=1&before={cursor}").json()
        assert second["has_more"] is False
        assert second["redemptions"][0]["member_id"] == one
        assert second["redemptions"][0]["id"] < cursor
        assert child.get(f"/api/members/{one}/points").json()["total"] == 80
        assert child.get(f"/api/members/{one}/progress").json() == expected
    finally:
        child.close()
