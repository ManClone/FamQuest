from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth_registry import AuthBase, Identity, Membership, OperatorSession, Tenant
from app.browser_sessions import COOKIE_NAME
from app.config import Settings
from app.multitenant_app import create_app
from app.operator_console import COOKIE
from app.operator_setup import create_operator
from app.security import hash_secret, token_hash

ORIGIN = "https://operator.example.test"
PASSWORD = "independent-operator-test-password"


class Registry:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        AuthBase.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        with Session(self.engine) as db:
            yield db


class NoFamilyAccess:
    def session(self, family):
        raise AssertionError("Operator routes must never open a family database")


@pytest.fixture
def setup():
    registry = Registry()
    with registry.session() as db:
        db.add_all(
            [
                Tenant(id=1, name="Sertl", database_name="famquest_sertl", status="active"),
                Tenant(
                    id=2,
                    name="Henning <script>alert(1)</script>",
                    database_name="famquest_henning",
                    status="disabled",
                ),
                Identity(id=1, email="parent@example.test", password_hash=hash_secret(PASSWORD)),
                Identity(id=2, email="child@example.test", password_hash=hash_secret(PASSWORD)),
            ]
        )
        db.flush()
        db.add_all(
            [
                Membership(identity_id=1, tenant_id=1, role="parent"),
                Membership(identity_id=2, tenant_id=1, role="child"),
            ]
        )
        create_operator(db, "operator@example.test", PASSWORD)
        db.commit()
    app = create_app(
        Settings(_env_file=None, public_url=ORIGIN),
        database=registry,
        family_router=NoFamilyAccess(),
    )
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        yield client, registry
    registry.engine.dispose()


def login(client, email="operator@example.test", password=PASSWORD):
    return client.post("/operator/api/login", json={"email": email, "password": password})


def test_operator_has_separate_secure_hashed_short_session_and_registry_only_overview(setup):
    client, registry = setup
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Max-Age=3600" in cookie and "Domain=" not in cookie
    raw = client.cookies.get(COOKIE)
    assert client.cookies.get(COOKIE_NAME) is None
    with registry.session() as db:
        stored = db.scalar(select(OperatorSession))
        assert stored.token_hash == token_hash(raw) and stored.token_hash != raw
    listing = client.get("/operator/api/families")
    assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
    assert [(x["status"], x["accounts"]) for x in listing.json()] == [
        ("disabled", 0),
        ("active", 2),
    ]
    assert "database_name" not in listing.text and "password" not in listing.text
    assert client.get("/api/members").status_code == 401
    assert client.get("/operator/api/session").json()["email"] == "operator@example.test"


@pytest.mark.parametrize(
    "email", ["parent@example.test", "child@example.test", "unknown@example.test"]
)
def test_family_credentials_never_grant_operator_access(setup, email):
    client, _ = setup
    assert login(client, email).status_code == 401
    assert client.get("/operator/api/families").status_code == 401
    assert client.cookies.get(COOKIE) is None


def test_family_cookie_bearer_and_spoofed_headers_cannot_grant_operator_access(setup):
    client, _ = setup
    client.cookies.set(COOKIE_NAME, "fake-family-session")
    assert (
        client.get(
            "/operator/api/families",
            headers={"authorization": "Bearer fake", "x-superadmin": "true", "x-family-id": "1"},
        ).status_code
        == 401
    )
    assert client.get("/operator/api/session").status_code == 401


@pytest.mark.parametrize("change", ["expired", "demoted", "membership", "deleted"])
def test_existing_operator_session_rechecks_authority_on_every_request(setup, change):
    client, registry = setup
    assert login(client).status_code == 200
    with registry.session() as db:
        identity = db.scalar(select(Identity).where(Identity.is_superadmin.is_(True)))
        if change == "expired":
            db.scalar(select(OperatorSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif change == "demoted":
            identity.is_superadmin = False
        elif change == "deleted":
            db.delete(identity)
        else:
            db.add(Membership(identity_id=identity.id, tenant_id=1, role="admin"))
        db.commit()
    assert client.get("/operator/api/families").status_code in (401, 403)


def test_logout_requires_csrf_revokes_session_and_cookie_rotation_invalidates_old_token(setup):
    client, _ = setup
    first = login(client)
    old = client.cookies.get(COOKIE)
    second = login(client)
    current = client.cookies.get(COOKIE)
    client.cookies.set(COOKIE, old, domain="operator.example.test", path="/")
    assert client.get("/operator/api/session").status_code == 401
    client.cookies.set(COOKIE, current, domain="operator.example.test", path="/")
    assert client.post("/operator/api/logout").status_code == 403
    assert (
        client.post(
            "/operator/api/logout", headers={"x-csrf-token": first.json()["csrf_token"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/operator/api/logout", headers={"x-csrf-token": second.json()["csrf_token"]}
        ).status_code
        == 204
    )
    assert client.get("/operator/api/session").status_code == 401


def test_origin_csrf_wrong_password_and_rate_limit(setup):
    client, _ = setup
    assert (
        client.post(
            "/operator/api/login",
            json={"email": "operator@example.test", "password": PASSWORD},
            headers={"origin": "https://evil.example.test"},
        ).status_code
        == 403
    )
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429


def test_page_and_assets_are_csp_protected_and_no_operator_mutations_exist(setup):
    client, _ = setup
    response = client.get("/operator")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    assert "Cache-Control" in response.headers
    js = client.get("/operator/assets/console.js")
    assert js.status_code == 200 and "textContent" in js.text and "innerHTML" not in js.text
    assert client.get("/operator/assets/console.css").status_code == 200
    assert client.get("/operator/assets/secret.env").status_code == 404
    assert login(client).status_code == 200
    assert client.post("/operator/api/families/1/disable").status_code == 404
    assert client.get("/operator/api/missing").status_code == 404


def test_setup_refuses_existing_identity_or_weak_password(setup):
    _, registry = setup
    with registry.session() as db:
        with pytest.raises(ValueError):
            create_operator(db, "parent@example.test", PASSWORD)
        with pytest.raises(ValueError):
            create_operator(db, "new@example.test", "short")
        assert not db.get(Identity, 1).is_superadmin


def test_reviewed_operator_migration_preserves_existing_registry_data(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.operator_setup import migrate_registry

    engine = create_engine(f"sqlite:///{tmp_path / 'operator-upgrade.sqlite'}")
    config = Config(Path(__file__).resolve().parents[1] / "auth_alembic.ini")
    config.attributes["database_url"] = engine.url
    command.upgrade(config, "e20261031_actors")
    try:
        with Session(engine) as db:
            db.add(
                Tenant(
                    id=1, name="Existing family", database_name="famquest_existing", status="active"
                )
            )
            db.add(
                Identity(
                    id=1,
                    email="existing@example.test",
                    password_hash="unchanged-hash",
                    is_superadmin=False,
                )
            )
            db.flush()
            db.add(Membership(identity_id=1, tenant_id=1, role="parent", family_user_id=7))
            db.commit()
        registry = type("MigrationRegistry", (), {"engine": engine})()
        migrate_registry(registry)
        migrate_registry(registry)
        with Session(engine) as db:
            assert db.get(Identity, 1).password_hash == "unchanged-hash"
            assert not db.get(Identity, 1).is_superadmin
            assert db.get(Tenant, 1).name == "Existing family"
            assert db.scalar(select(Membership)).family_user_id == 7
            assert list(db.scalars(select(OperatorSession))) == []
            db.execute(text("UPDATE alembic_version SET version_num='unexpected'"))
            db.commit()
        with pytest.raises(ValueError):
            migrate_registry(registry)
    finally:
        engine.dispose()
