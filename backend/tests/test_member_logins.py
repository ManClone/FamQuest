from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import FamilyMember
from tests.conftest import csrf

PROFILE = {"name": "Tom", "role": "child", "color": "green"}
LOGIN = {"email": "tom@example.org", "password": "test-password-123"}


def test_create_person_and_login_atomically(client, parent):
    response = client.post("/api/members", json={**PROFILE, "login": LOGIN}, headers=csrf(parent))
    assert response.status_code == 201, response.text
    member_id = response.json()["id"]
    accounts = client.get("/api/auth/accounts").json()
    account = next(a for a in accounts if a["email"] == LOGIN["email"])
    assert account["member_id"] == member_id
    assert account["role"] == "child"
    assert client.post("/api/auth/logout", headers=csrf(parent)).status_code == 204
    assert client.post("/api/auth/login", json=LOGIN).status_code == 200
    assert client.get("/api/auth/accounts").status_code == 403
    assert client.put(f"/api/members/{member_id}", json=PROFILE).status_code == 403


def test_duplicate_email_does_not_create_person(client, parent):
    email = parent["user"]["email"]
    response = client.post(
        "/api/members", json={**PROFILE, "login": {**LOGIN, "email": email}}, headers=csrf(parent)
    )
    assert response.status_code == 409
    assert client.get("/api/members").json() == []


def test_existing_account_can_only_be_linked_once(client, parent):
    account = client.post(
        "/api/auth/accounts", json={**LOGIN, "role": "child"}, headers=csrf(parent)
    ).json()
    payload = {**PROFILE, "login": {"account_id": account["id"]}}
    first = client.post("/api/members", json=payload, headers=csrf(parent))
    assert first.status_code == 201, first.text
    second = client.post("/api/members", json={**payload, "color": "blue"}, headers=csrf(parent))
    assert second.status_code == 409
    assert len(client.get("/api/members").json()) == 1


def test_change_email_preserves_password_and_password_can_be_reset(client, parent):
    created = client.post("/api/members", json={**PROFILE, "login": LOGIN}, headers=csrf(parent))
    member_id = created.json()["id"]
    url = f"/api/members/{member_id}"
    updated = {**PROFILE, "login": {"email": "new@example.org"}}
    assert client.put(url, json=updated, headers=csrf(parent)).status_code == 200
    updated["login"]["password"] = "changed-password-123"
    assert client.put(url, json=updated, headers=csrf(parent)).status_code == 200
    client.cookies.clear()
    assert (
        client.post("/api/auth/login", json={**LOGIN, "email": "new@example.org"}).status_code
        == 401
    )
    assert client.post("/api/auth/login", json=updated["login"]).status_code == 200


def test_admin_link_cannot_be_demoted(client, parent):
    account = client.get("/api/auth/accounts").json()[0]
    profile = {**PROFILE, "role": "parent", "login": {"account_id": account["id"]}}
    created = client.post("/api/members", json=profile, headers=csrf(parent))
    assert created.status_code == 201, created.text
    member_id = created.json()["id"]
    assert (
        client.put(f"/api/members/{member_id}", json=PROFILE, headers=csrf(parent)).status_code
        == 409
    )
    with Session(engine) as db:
        assert db.scalar(select(FamilyMember.role).where(FamilyMember.id == member_id)) == "parent"


def test_demo_rejects_login_without_creating_person(client, parent, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_mode", "de")
    response = client.post("/api/members", json={**PROFILE, "login": LOGIN}, headers=csrf(parent))
    assert response.status_code == 403
    assert client.get("/api/members").json() == []


def test_new_login_requires_password_without_partial_profile(client, parent):
    response = client.post(
        "/api/members", json={**PROFILE, "login": {"email": LOGIN["email"]}}, headers=csrf(parent)
    )
    assert response.status_code == 422
    assert client.get("/api/members").json() == []


def test_existing_parent_login_cannot_be_assigned_to_child(client, parent):
    account = client.get("/api/auth/accounts").json()[0]
    response = client.post(
        "/api/members",
        json={**PROFILE, "login": {"account_id": account["id"]}},
        headers=csrf(parent),
    )
    assert response.status_code == 409
    assert client.get("/api/members").json() == []


def test_role_change_revokes_sessions_and_updates_permissions(client, parent):
    created = client.post("/api/members", json={**PROFILE, "login": LOGIN}, headers=csrf(parent))
    member_id = created.json()["id"]
    other = TestClient(client.app)
    try:
        assert other.post("/api/auth/login", json=LOGIN).status_code == 200
        assert other.get("/api/auth/accounts").status_code == 403
        response = client.put(
            f"/api/members/{member_id}", json={**PROFILE, "role": "parent"}, headers=csrf(parent)
        )
        assert response.status_code == 200, response.text
        assert other.get("/api/auth/me").status_code == 401
        assert other.post("/api/auth/login", json=LOGIN).json()["user"]["role"] == "parent"
        assert other.get("/api/auth/accounts").status_code == 200
    finally:
        other.close()
