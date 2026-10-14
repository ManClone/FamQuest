"""Regressionstests für getrennte Benutzerkonten und Demo-Schutz."""

from app.config import get_settings
from tests.conftest import csrf


def test_account_management_requires_parent_role(client, admin):
    payload = {"email": "tim@example.org", "password": "sehr-geheim-456", "role": "child"}
    assert client.post("/api/auth/accounts", json=payload, headers=csrf(admin)).status_code == 201
    assert client.get("/api/auth/accounts").status_code == 200

    assert client.post("/api/auth/logout", headers=csrf(admin)).status_code == 204
    child = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]}).json()
    assert client.get("/api/auth/accounts").status_code == 403
    assert client.post(
        "/api/auth/accounts",
        json={"email": "other@example.org", "password": "sehr-geheim-789", "role": "parent"},
        headers=csrf(child),
    ).status_code == 403


def test_account_management_requires_login(client):
    assert client.get("/api/auth/accounts").status_code == 401


def test_account_management_blocks_demo(client, admin, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", "de")
    assert client.get("/api/auth/accounts").status_code == 403
    assert client.get("/api/auth/accounts").json() == {"code": "demo.disabled"}
    response = client.post(
        "/api/auth/accounts",
        json={"email": "tim@example.org", "password": "sehr-geheim-456", "role": "child"},
        headers=csrf(admin),
    )
    assert response.status_code == 403
    assert response.json() == {"code": "demo.disabled"}


def test_account_creation_rejects_duplicates_and_invalid_roles(client, admin):
    payload = {"email": "tim@example.org", "password": "sehr-geheim-456", "role": "child"}
    assert client.post("/api/auth/accounts", json=payload, headers=csrf(admin)).status_code == 201
    assert client.post("/api/auth/accounts", json=payload, headers=csrf(admin)).status_code == 409
    assert client.post(
        "/api/auth/accounts",
        json={**payload, "email": "another@example.org", "role": "admin"},
        headers=csrf(admin),
    ).status_code == 422
