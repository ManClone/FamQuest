"""Central login HTTP tests with separate Sertl/Henning identities."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth_registry import (
    AuthBase,
    BrowserSession,
    Identity,
    Membership,
    OAuthClient,
    OAuthGrant,
    Tenant,
)
from app.browser_sessions import COOKIE_NAME
from app.central_auth import create_app
from app.config import Settings
from app.security import hash_secret, token_hash

ORIGIN = "https://family.example.invalid"
PASSWORD = "test-only-password-123"


class TestRegistry:
    __test__ = False

    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def session(self):
        with Session(self.engine) as db:
            yield db


@pytest.fixture
def registry():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    AuthBase.metadata.create_all(engine)
    with Session(engine) as db:
        password_hash = hash_secret(PASSWORD)
        db.add_all(
            [
                Tenant(id=1, name="Sertl", database_name="famquest_sertl", status="active"),
                Tenant(id=2, name="Henning", database_name="famquest_henning", status="active"),
                Identity(id=1, email="sertl@example.invalid", password_hash=password_hash),
                Identity(id=2, email="henning@example.invalid", password_hash=password_hash),
            ]
        )
        db.flush()
        db.add_all(
            [
                Membership(identity_id=1, tenant_id=1, role="parent"),
                Membership(identity_id=2, tenant_id=2, role="child"),
            ]
        )
        db.commit()
    yield TestRegistry(engine)
    engine.dispose()


@pytest.fixture
def app(registry):
    return create_app(Settings(public_url=ORIGIN), database=registry)


@pytest.fixture
def client(app):
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        yield client


def login(client, email="sertl@example.invalid", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_session_cookie_is_secure_hashed_and_family_is_server_selected(client, registry):
    response = login(client)
    assert response.status_code == 200
    assert response.json()["family_name"] == "Sertl"
    assert "database_name" not in response.text
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Domain=" not in cookie and "Path=/" in cookie
    assert response.headers["cache-control"] == "no-store"
    raw = client.cookies.get(COOKIE_NAME)
    with registry.session() as db:
        session = db.scalar(select(BrowserSession))
        assert session.token_hash == token_hash(raw)
        assert session.token_hash != raw
        assert session.tenant_id == 1
    me = client.get("/api/auth/me", headers={"x-family-id": "2", "x-database": "famquest_henning"})
    assert me.status_code == 200
    assert me.json()["family_name"] == "Sertl"
    login(client, email="henning@example.invalid")
    assert client.get("/api/auth/me").json()["family_name"] == "Henning"
    assert client.get("/api/auth/me").json()["role"] == "child"


def test_logout_requires_origin_and_csrf_and_revokes_server_session(client):
    response = login(client)
    raw = client.cookies.get(COOKIE_NAME)
    csrf = response.json()["csrf_token"]
    assert client.post("/api/auth/logout").status_code == 403
    assert (
        client.post(
            "/api/auth/logout", headers={"origin": "https://evil.invalid", "x-csrf-token": csrf}
        ).status_code
        == 403
    )
    assert client.post("/api/auth/logout", headers={"x-csrf-token": csrf}).status_code == 204
    client.cookies.set(COOKIE_NAME, raw)
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("change", ["disabled", "removed", "reassigned", "superadmin", "multiple"])
def test_existing_session_cannot_survive_invalid_family_membership(client, registry, change):
    assert login(client).status_code == 200
    with registry.session() as db:
        membership = db.scalar(select(Membership).where(Membership.identity_id == 1))
        if change == "disabled":
            db.get(Tenant, 1).status = "disabled"
        elif change == "removed":
            db.delete(membership)
        elif change == "reassigned":
            membership.tenant_id = 2
        elif change == "superadmin":
            db.get(Identity, 1).is_superadmin = True
        else:
            db.add(Membership(identity_id=1, tenant_id=2, role="parent"))
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_session_expiration_and_unknown_tokens(client, registry):
    assert client.get("/api/auth/me").status_code == 401
    assert login(client).status_code == 200
    with registry.session() as db:
        db.scalar(select(BrowserSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_password_change_revokes_all_browser_and_connector_sessions(client, registry, app):
    first = login(client)
    old_cookie = client.cookies.get(COOKIE_NAME)
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as other:
        assert login(other).status_code == 200
        with registry.session() as db:
            db.add(
                OAuthClient(id="client", redirect_uri="https://example.invalid/cb", enabled=True)
            )
            db.flush()
            db.add(
                OAuthGrant(
                    id="grant",
                    client_id="client",
                    identity_id=1,
                    tenant_id=1,
                    audience="https://example.invalid/mcp",
                )
            )
            db.commit()
        result = client.put(
            "/api/auth/password",
            json={"current_password": PASSWORD, "new_password": "new-test-password-123"},
            headers={"x-csrf-token": first.json()["csrf_token"]},
        )
        assert result.status_code == 204
        assert other.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE_NAME, old_cookie)
    assert client.get("/api/auth/me").status_code == 401
    assert login(client).status_code == 401
    assert login(client, password="new-test-password-123").status_code == 200
    with registry.session() as db:
        assert db.get(OAuthGrant, "grant").revoked_at is not None


def test_invalid_password_change_preserves_session_and_is_rate_limited(client):
    csrf = login(client).json()["csrf_token"]
    for _ in range(5):
        response = client.put(
            "/api/auth/password",
            headers={"x-csrf-token": csrf},
            json={"current_password": "wrong", "new_password": "new-test-pass"},
        )
        assert response.status_code == 403
    response = client.put(
        "/api/auth/password",
        headers={"x-csrf-token": csrf},
        json={"current_password": PASSWORD, "new_password": "new-test-pass"},
    )
    assert response.status_code == 429
    assert client.get("/api/auth/me").status_code == 200


def test_login_rate_limit_and_generic_error(client):
    for _ in range(5):
        response = login(client, password="wrong")
        assert response.status_code == 401
        assert response.json() == {"code": "auth.invalid_credentials"}
    assert login(client).status_code == 429


@pytest.mark.parametrize(
    "url",
    [
        "http://family.invalid",
        "",
        "https://family.invalid/path",
        "https://user:password@family.invalid",
    ],
)
def test_insecure_or_ambiguous_origin_prevents_startup(url, registry):
    with pytest.raises(ValueError, match="HTTPS origin"):
        create_app(Settings(public_url=url), database=registry)


def test_legacy_cookie_does_not_authenticate_central_service(client):
    client.cookies.set("famquest_session", "legacy-token")
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/members").status_code == 404
