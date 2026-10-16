"""The service boundary never grants rights from a client-supplied role."""

from app.config import get_settings
from app.mcp_access import allowed
from tests.conftest import csrf


def service_headers(parent_id):
    return {"Authorization": "Bearer " + "s" * 40, "X-FamQuest-Parent-ID": str(parent_id)}


def test_service_disabled_invalid_and_child_principals_denied(client, parent, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_service_token", "")
    assert client.get("/api/tasks", headers=service_headers(1)).status_code == 401
    monkeypatch.setattr(settings, "mcp_service_token", "s" * 40)
    assert client.get("/api/tasks", headers=service_headers(99999)).status_code == 403
    client.post(
        "/api/auth/accounts",
        json={
            "email": "mcp-child@example.org",
            "password": "test-password-456",
            "role": "child",
        },
        headers=csrf(parent),
    ).json()
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        child_id = db.scalar(select(User.id).where(User.email == "mcp-child@example.org"))
    assert client.get("/api/tasks", headers=service_headers(child_id)).status_code == 403


def test_service_parent_uses_real_task_parameters_but_cannot_manage_accounts(
    client, parent, lena, monkeypatch
):
    monkeypatch.setattr(get_settings(), "mcp_service_token", "s" * 40)
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        owner = db.scalar(select(User.id).where(User.role == "admin"))
    headers = service_headers(owner)
    response = client.get("/api/internal/mcp/schema", headers=headers)
    assert response.status_code == 200, response.text
    spec = response.json()
    assert "/api/tasks/schedule" in spec["paths"]
    assert "/api/chores/weekly-confirmed" in spec["paths"]
    assert "/api/maintenance/consistency" in spec["paths"]
    for path in (
        "/api/members/{member_id}/points/{transaction_id}/reverse",
        "/api/members/{member_id}/penalties/{transaction_id}/reverse",
        "/api/members/{member_id}/praise/{praise_id}/revoke",
    ):
        operation = spec["paths"][path]["post"]
        assert any(
            p["name"] == "X-MCP-Parent-Confirmed" and p["required"] for p in operation["parameters"]
        )
    assert "/api/auth/accounts" not in spec["paths"]
    assert client.post("/api/auth/accounts", json={}, headers=headers).status_code == 403
    assert client.put("/api/profile/password", json={}, headers=headers).status_code == 403
    assert client.post("/api/approvals/1", headers=headers).status_code == 409
    praise = client.post(
        f"/api/members/{lena}/praise",
        json={"reason": "Test", "request_key": "d" * 32},
        headers=headers,
    ).json()
    revoke_path = f"/api/members/{lena}/praise/{praise['id']}/revoke"
    assert (
        client.post(revoke_path, json={"reason": "Test entry"}, headers=headers).status_code == 409
    )
    assert (
        client.post(
            revoke_path,
            json={"reason": "Test entry"},
            headers={**headers, "X-MCP-Parent-Confirmed": "true"},
        ).status_code
        == 200
    )
    from tests.test_tasks import task_data

    payload = task_data(
        [lena],
        title="Read together",
        points=7,
        repeatable=True,
        needs_approval=True,
        recurrence={"kind": "weekly", "weekdays": [1, 3, 5]},
    )
    saved = client.post(
        "/api/tasks/schedule",
        json={"task": payload, "times": ["morning", "evening"]},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    tasks = client.get("/api/tasks", headers=headers).json()
    assert len(tasks) == 2
    assert {item["time_of_day"] for item in tasks} == {"morning", "evening"}
    assert all(
        item["points"] == 7 and item["repeatable"] and item["needs_approval"] for item in tasks
    )
    assert all(item["recurrence"]["weekdays"] == [1, 3, 5] for item in tasks)


def test_schema_and_runtime_allowlist_agree_on_sensitive_operations():
    for path in (
        "/api/auth/accounts",
        "/api/profile/password",
        "/api/internal/quest-import",
        "/api/members/1/money",
        "/api/calendar/google/connect",
    ):
        assert not allowed("POST", path)
    assert allowed("POST", "/api/tasks/schedule")
    assert allowed("POST", "/api/chores/weekly-confirmed")
    assert not allowed("POST", "/api/chores/1/credit")
