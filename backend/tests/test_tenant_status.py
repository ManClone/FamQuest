from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.auth_registry import Identity, Membership, OAuthClient, Tenant, TenantStatusEvent
from app.browser_sessions import authenticate_browser, login_browser
from app.oauth_codes import consume_code, issue_code
from app.oauth_pkce import s256_challenge
from app.oauth_tokens import authenticate_access, rotate_refresh
from app.operator_setup import migrate_status_registry
from app.security import hash_secret
from tests.test_oauth_tokens import AUDIENCE, REDIRECT, pair
from tests.test_operator_console import PASSWORD, login
from tests.test_operator_console import setup as setup


def body(status="disabled", expected="active", name="Sertl", **extra):
    return {
        "status": status,
        "expected_status": expected,
        "family_name": name,
        "reason": "Operator test reason",
        "confirmed": True,
        "request_key": str(uuid4()),
        **extra,
    }


def authorize(client):
    response = login(client)
    assert response.status_code == 200
    return {"x-csrf-token": response.json()["csrf_token"]}


def test_confirmed_status_change_has_actor_audit_and_idempotent_replay(setup):
    client, registry = setup
    headers = authorize(client)
    request = body()
    first = client.post("/operator/api/families/1/status", json=request, headers=headers)
    assert first.status_code == 200
    assert (
        client.post("/operator/api/families/1/status", json=request, headers=headers).json()
        == first.json()
    )
    assert (
        client.post("/operator/api/families/1/status", json=body(), headers=headers).status_code
        == 409
    )
    with registry.session() as db:
        assert db.get(Tenant, 1).status == "disabled"
        events = list(db.scalars(select(TenantStatusEvent)))
        assert len(events) == 1 and events[0].actor_identity_id == 3
        assert events[0].from_status == "active" and events[0].reason == request["reason"]
    assert (
        client.post(
            "/operator/api/families/1/status",
            json={**request, "reason": "different"},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/operator/api/families/1/status", json=body("active", "disabled"), headers=headers
        ).status_code
        == 200
    )
    # Retrying the old action must not suspend a reactivated family a second time.
    assert (
        client.post("/operator/api/families/1/status", json=request, headers=headers).status_code
        == 200
    )
    with registry.session() as db:
        assert db.get(Tenant, 1).status == "active"
        assert len(list(db.scalars(select(TenantStatusEvent)))) == 2
    history = client.get("/operator/api/families/1/history").json()
    assert [event["to_status"] for event in history["items"]] == ["active", "disabled"]
    assert all(event["actor_email"] == "operator@example.test" for event in history["items"])


@pytest.mark.parametrize(
    "extra",
    [
        {"confirmed": False},
        {"reason": "   "},
        {"reason": "x" * 501},
        {"status": "provisioning"},
        {"actor_identity_id": 1},
        {"request_key": "invalid"},
    ],
)
def test_invalid_or_unconfirmed_changes_are_rejected(setup, extra):
    client, registry = setup
    headers = authorize(client)
    assert (
        client.post(
            "/operator/api/families/1/status", json=body(**extra), headers=headers
        ).status_code
        == 422
    )
    with registry.session() as db:
        assert db.get(Tenant, 1).status == "active"
        assert list(db.scalars(select(TenantStatusEvent))) == []


def test_status_requires_csrf_exact_name_and_current_supported_state(setup):
    client, registry = setup
    headers = authorize(client)
    assert client.post("/operator/api/families/1/status", json=body()).status_code == 403
    assert (
        client.post(
            "/operator/api/families/1/status", json=body(name="Henning"), headers=headers
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/operator/api/families/1/status", json=body("active"), headers=headers
        ).status_code
        == 409
    )
    assert (
        client.post("/operator/api/families/999/status", json=body(), headers=headers).status_code
        == 404
    )
    with registry.session() as db:
        db.get(Tenant, 1).status = "provisioning"
        db.commit()
    assert (
        client.post(
            "/operator/api/families/1/status", json=body("active", "disabled"), headers=headers
        ).status_code
        == 409
    )


def test_family_credentials_cannot_write_or_read_operator_history(setup):
    client, _ = setup
    assert login(client, email="parent@example.test").status_code == 401
    assert client.post("/operator/api/families/1/status", json=body()).status_code == 401
    assert client.get("/operator/api/families/1/history").status_code == 401


def test_suspend_revokes_browser_and_mcp_permanently_but_preserves_other_family(setup):
    client, registry = setup
    with registry.session() as db:
        db.add(OAuthClient(id="client", redirect_uri=REDIRECT, enabled=True))
        db.get(Tenant, 2).status = "active"
        db.add(Identity(id=4, email="other@example.test", password_hash=hash_secret(PASSWORD)))
        db.flush()
        db.add(Membership(identity_id=4, tenant_id=2, role="parent"))
        db.commit()
        browser, _ = login_browser(db, "parent@example.test", PASSWORD)
        db.commit()
        other, _ = login_browser(db, "other@example.test", PASSWORD)
        db.commit()
        tokens = pair(db)
        code = issue_code(
            db,
            client_id="client",
            redirect_uri=REDIRECT,
            identity_id=1,
            tenant_id=1,
            code_challenge=s256_challenge("v" * 43),
        )
        db.commit()
    headers = authorize(client)
    assert (
        client.post("/operator/api/families/1/status", json=body(), headers=headers).status_code
        == 200
    )
    with registry.session() as db:
        with pytest.raises(PermissionError):
            authenticate_browser(db, browser)
        assert authenticate_browser(db, other)[1].tenant_id == 2
        with pytest.raises(PermissionError):
            login_browser(db, "parent@example.test", PASSWORD)
    assert (
        client.post(
            "/operator/api/families/1/status", json=body("active", "disabled"), headers=headers
        ).status_code
        == 200
    )
    with registry.session() as db:
        with pytest.raises(PermissionError):
            authenticate_browser(db, browser)
        with pytest.raises(PermissionError):
            authenticate_access(db, tokens.access_token, audience=AUDIENCE)
        db.rollback()
        with pytest.raises(PermissionError):
            rotate_refresh(db, tokens.refresh_token, client_id="client", audience=AUDIENCE)
        with pytest.raises(PermissionError):
            consume_code(
                db, code=code, client_id="client", redirect_uri=REDIRECT, verifier="v" * 43
            )
        db.rollback()
        fresh, _ = login_browser(db, "parent@example.test", PASSWORD)
        db.commit()
        assert authenticate_browser(db, fresh)[1].tenant_id == 1


def test_history_cursor_preserves_order_and_no_mutation_endpoints_exist(setup):
    client, _ = setup
    headers = authorize(client)
    for index in range(53):
        status, previous = ("disabled", "active") if index % 2 == 0 else ("active", "disabled")
        assert (
            client.post(
                "/operator/api/families/1/status", json=body(status, previous), headers=headers
            ).status_code
            == 200
        )
    first = client.get("/operator/api/families/1/history").json()
    assert len(first["items"]) == 50 and first["next_before"]
    last = client.get(f"/operator/api/families/1/history?before={first['next_before']}").json()
    assert len(last["items"]) == 3 and last["next_before"] is None
    assert len({event["id"] for event in first["items"] + last["items"]}) == 53
    assert client.delete("/operator/api/families/1/history", headers=headers).status_code == 404


def test_additive_status_migration_preserves_operator_and_family_registry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'status-migration.sqlite'}")
    config = Config(Path(__file__).resolve().parents[1] / "auth_alembic.ini")
    config.attributes["database_url"] = engine.url
    command.upgrade(config, "f20261101_operator")
    try:
        with Session(engine) as db:
            db.add(
                Tenant(id=1, name="Existing", database_name="famquest_existing", status="active")
            )
            db.add(
                Identity(
                    id=1,
                    email="operator@example.test",
                    password_hash="unchanged",
                    is_superadmin=True,
                )
            )
            db.commit()
        registry = type("MigrationRegistry", (), {"engine": engine})()
        migrate_status_registry(registry)
        migrate_status_registry(registry)
        with Session(engine) as db:
            assert (
                db.get(Identity, 1).is_superadmin
                and db.get(Identity, 1).password_hash == "unchanged"
            )
            assert db.get(Tenant, 1).status == "active"
            assert list(db.scalars(select(TenantStatusEvent))) == []
            db.execute(text("UPDATE alembic_version SET version_num='unexpected'"))
            db.commit()
        with pytest.raises(ValueError):
            migrate_status_registry(registry)
    finally:
        engine.dispose()
