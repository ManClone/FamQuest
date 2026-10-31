"""Real HTTP requests against separate auth and family database connections.

SQLite exercises the routing boundary locally. Full PostgreSQL schemas and role
permissions are covered separately; this fixture creates only profile tables.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, MetaData, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.auth_registry import AuthBase, Identity, Membership, Tenant
from app.config import Settings
from app.models import Family, FamilyMember, User
from app.multitenant_app import create_app
from app.security import hash_secret
from tests.test_central_auth import ORIGIN, PASSWORD, TestRegistry


class TestFamilyRouter:
    __test__ = False

    def __init__(self, engines):
        self.engines = engines

    @contextmanager
    def session(self, family):
        with Session(self.engines[family.database_name]) as db:
            yield db


@pytest.fixture
def environment(tmp_path):
    database_names = iter(("registry", "sertl", "henning"))

    def engine():
        return create_engine(
            f"sqlite:///{tmp_path / (next(database_names) + '.sqlite')}",
            connect_args={"check_same_thread": False},
        )

    registry_engine = engine()
    AuthBase.metadata.create_all(registry_engine)
    family_engines = {}
    filename = "a" * 32 + ".webp"
    for tenant_id, name in ((1, "Sertl"), (2, "Henning")):
        family_engine = engine()
        metadata = MetaData()
        for model in (Family, User, FamilyMember):
            table = model.__table__.to_metadata(metadata)
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
        metadata.create_all(family_engine)
        with Session(family_engine) as db:
            db.add(Family(id=1, name=name, default_language="de"))
            db.flush()
            db.add(
                User(
                    id=1,
                    family_id=1,
                    email=f"{name.lower()}@example.invalid",
                    role="parent",
                    password_hash="!",
                )
            )
            db.flush()
            db.add(
                FamilyMember(
                    id=1,
                    name=f"Parent {name}",
                    role="parent",
                    color="blue",
                    user_id=1,
                    avatar=filename,
                )
            )
            db.commit()
        family_engines[f"famquest_{name.lower()}"] = family_engine
        directory = tmp_path / "families" / str(tenant_id) / "avatars"
        directory.mkdir(parents=True)
        (directory / filename).write_bytes(name.encode())
    with Session(registry_engine) as db:
        secret = hash_secret(PASSWORD)
        for tenant_id, name in ((1, "Sertl"), (2, "Henning")):
            db.add(
                Tenant(
                    id=tenant_id,
                    name=name,
                    database_name=f"famquest_{name.lower()}",
                    status="active",
                )
            )
            db.add(
                Identity(
                    id=tenant_id, email=f"{name.lower()}@example.invalid", password_hash=secret
                )
            )
        db.flush()
        for tenant_id in (1, 2):
            db.add(
                Membership(
                    identity_id=tenant_id, tenant_id=tenant_id, role="parent", family_user_id=1
                )
            )
        db.commit()
    registry = TestRegistry(registry_engine)
    router = TestFamilyRouter(family_engines)
    app = create_app(
        Settings(public_url=ORIGIN, upload_dir=tmp_path), database=registry, family_router=router
    )
    yield app, registry, router, filename
    registry_engine.dispose()
    for item in family_engines.values():
        item.dispose()


def login(client, name):
    result = client.post(
        "/api/auth/login", json={"email": f"{name.lower()}@example.invalid", "password": PASSWORD}
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_login_matches_existing_frontend_and_binds_family_local_actor(environment):
    app, _, _, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        me = login(client, "Henning")
        assert me["family"]["name"] == "Henning"
        assert me["member_id"] == 1
        assert me["user"]["email"] == "henning@example.invalid"
        assert me["parent_unlocked"] is True
        assert client.get("/api/auth/me").json() == me
        assert client.get("/api/setup/status").json() == {"setup_required": False, "demo": None}


def test_simultaneous_families_cannot_read_or_mutate_each_other(environment):
    app, _, _, _ = environment
    with (
        TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as sertl,
        TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as henning,
    ):
        a, b = login(sertl, "Sertl"), login(henning, "Henning")

        def read(client):
            return client.get(
                "/api/members", headers={"x-family-id": "2", "x-famquest-parent-id": "2"}
            ).json()[0]["name"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(read, [sertl, henning])) == ["Parent Sertl", "Parent Henning"]
        response = sertl.put(
            "/api/parent/family",
            headers={"x-csrf-token": a["csrf_token"]},
            json={"name": "Changed Sertl", "default_language": "de", "timezone": "Europe/Berlin"},
        )
        assert response.status_code == 200, response.text
        assert henning.get("/api/auth/me").json()["family"]["name"] == "Henning"
        assert sertl.get("/api/auth/me").json()["family"]["name"] == "Changed Sertl"
        assert (
            henning.put(
                "/api/parent/family",
                headers={"x-csrf-token": a["csrf_token"]},
                json={"name": "Invalid", "default_language": "de", "timezone": "Europe/Berlin"},
            ).status_code
            == 403
        )
        assert b["csrf_token"] != a["csrf_token"]


def test_same_avatar_filename_is_isolated_and_not_cached_across_logins(environment):
    app, _, _, filename = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        login(client, "Sertl")
        response = client.get(f"/api/avatars/{filename}")
        assert response.status_code == 200 and response.content == b"Sertl"
        assert response.headers["cache-control"] == "no-store"
        login(client, "Henning")
        response = client.get(f"/api/avatars/{filename}")
        assert response.status_code == 200 and response.content == b"Henning"


def test_disabled_family_and_missing_actor_mapping_fail_closed(environment):
    app, registry, _, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        login(client, "Sertl")
        with registry.session() as db:
            db.get(Tenant, 1).status = "disabled"
            db.commit()
        assert client.get("/api/members").status_code == 401
        with registry.session() as db:
            db.get(Tenant, 1).status = "active"
            from sqlalchemy import select

            db.scalar(select(Membership).where(Membership.tenant_id == 1)).family_user_id = None
            db.commit()
        assert client.get("/api/members").status_code == 403


def test_legacy_mcp_service_token_and_unmapped_parent_headers_cannot_authenticate(environment):
    app, _, _, _ = environment
    with TestClient(app, base_url=ORIGIN) as client:
        assert (
            client.get(
                "/api/members",
                headers={"authorization": "Bearer legacy-token", "x-famquest-parent-id": "1"},
            ).status_code
            == 401
        )
        assert client.get("/api/members").status_code == 401


def test_old_demo_configuration_is_rejected_instead_of_silently_blocking_writes(environment):
    _, registry, router, _ = environment
    with pytest.raises(ValueError, match="Demo mode"):
        create_app(
            Settings(public_url=ORIGIN, demo_mode="de"), database=registry, family_router=router
        )


def test_mcp_token_uses_its_registered_family_and_never_a_parent_header(environment):
    from app.auth_registry import OAuthClient
    from app.oauth_codes import issue_code
    from app.oauth_pkce import s256_challenge
    from app.oauth_tokens import exchange_code

    app, registry, _, _ = environment
    with registry.session() as db:
        db.add(OAuthClient(id="mcp-test", redirect_uri=ORIGIN + "/callback", enabled=True))
        db.commit()
        code = issue_code(
            db,
            client_id="mcp-test",
            redirect_uri=ORIGIN + "/callback",
            identity_id=1,
            tenant_id=1,
            code_challenge=s256_challenge("v" * 43),
        )
        db.commit()
        tokens = exchange_code(
            db,
            code=code,
            client_id="mcp-test",
            redirect_uri=ORIGIN + "/callback",
            verifier="v" * 43,
            audience=ORIGIN + "/mcp",
        )
    headers = {"authorization": "Bearer " + tokens.access_token, "x-famquest-parent-id": "2"}
    with TestClient(app, base_url=ORIGIN, headers=headers) as client:
        assert client.get("/api/members").json()[0]["name"] == "Parent Sertl"
        assert client.post("/api/chore-approvals/1").status_code == 409
        assert (
            client.post(
                "/api/chore-approvals/1", headers={"x-mcp-parent-confirmed": "true"}
            ).status_code
            == 503
        )


def test_calendar_operation_keeps_explicit_family_engine_and_checks_deactivation(
    environment, monkeypatch
):
    from types import SimpleNamespace

    from app.api import calendar
    from app.family_db import FamilyDatabase
    from app.family_principal import FamilyPrincipal

    app, registry, router, _ = environment
    principal = FamilyPrincipal(1, 1, "famquest_sertl", "parent", family_user_id=1)
    request = SimpleNamespace(app=app, state=SimpleNamespace(family_principal=principal))
    calls = []

    def sync(**kwargs):
        with kwargs["session_factory"]() as db:
            assert db.get(Family, 1).name == "Sertl"
            assert db.get_bind() is kwargs["database_engine"]
        calls.append(True)
        return True

    monkeypatch.setattr(calendar, "sync_all", sync)
    with router.session(FamilyDatabase(1, "famquest_sertl")) as db:
        job = calendar.sync_operation(request, db)
    assert job() is True
    with registry.session() as db:
        db.get(Tenant, 1).status = "disabled"
        db.commit()
    assert job() is False
    assert calls == [True]


def test_old_pin_flag_does_not_lock_out_an_authenticated_parent(environment):
    from app.family_db import FamilyDatabase

    app, _, router, _ = environment
    with router.session(FamilyDatabase(1, "famquest_sertl")) as db:
        db.get(Family, 1).pin_enabled = True
        db.commit()
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        me = login(client, "Sertl")
        assert me["parent_unlocked"] is True
        assert client.get("/api/members").status_code == 200


def test_profile_password_route_updates_only_central_credentials(environment):
    from app.family_db import FamilyDatabase

    app, _, router, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        me = login(client, "Sertl")
        result = client.put(
            "/api/profile/password",
            headers={"x-csrf-token": me["csrf_token"]},
            json={"current_password": PASSWORD, "new_password": "changed-password-123"},
        )
        assert result.status_code == 204, result.text
        assert client.get("/api/auth/me").status_code == 401
    with router.session(FamilyDatabase(1, "famquest_sertl")) as db:
        assert db.get(User, 1).password_hash == "!"


def child_payload():
    return {
        "name": "Tim",
        "role": "child",
        "color": "purple",
        "login": {"email": "tim@example.invalid", "password": "child-password-123"},
    }


def test_central_member_login_keeps_secrets_out_of_family_db_and_limits_child_access(environment):
    from sqlalchemy import select

    from app.family_db import FamilyDatabase
    from app.security import verify_secret

    app, registry, router, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as parent:
        me = login(parent, "Sertl")
        created = parent.post(
            "/api/members", json=child_payload(), headers={"x-csrf-token": me["csrf_token"]}
        )
        assert created.status_code == 201, created.text
        child_id = created.json()["id"]
        accounts = parent.get("/api/auth/accounts").json()
        assert {account["email"] for account in accounts} == {
            "sertl@example.invalid",
            "tim@example.invalid",
        }
        assert all(account["email"] != "henning@example.invalid" for account in accounts)
        with registry.session() as db:
            identity = db.scalar(select(Identity).where(Identity.email == "tim@example.invalid"))
            assert verify_secret(identity.password_hash, "child-password-123")
            assert identity.id != child_id  # Central and local IDs are deliberately different.
        with router.session(FamilyDatabase(1, "famquest_sertl")) as db:
            assert db.get(FamilyMember, child_id).user_id == 2
            assert db.get(User, 2).password_hash == "!"
        with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as child:
            result = child.post("/api/auth/login", json=child_payload()["login"])
            assert result.status_code == 200, result.text
            assert result.json()["member_id"] == child_id
            assert [member["id"] for member in child.get("/api/members").json()] == [child_id]
            assert child.get("/api/auth/accounts").status_code == 403
            assert (
                child.post(
                    "/api/members",
                    json=child_payload(),
                    headers={"x-csrf-token": result.json()["csrf_token"]},
                ).status_code
                == 403
            )


def test_create_unlinked_central_account_and_link_it_by_family_local_id(environment):
    app, _, _, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        me = login(client, "Sertl")
        headers = {"x-csrf-token": me["csrf_token"]}
        account = client.post(
            "/api/auth/accounts",
            headers=headers,
            json={
                "email": "tim@example.invalid",
                "password": "child-password-123",
                "role": "child",
            },
        )
        assert account.status_code == 201, account.text
        assert account.json()["member_id"] is None
        created = client.post(
            "/api/members",
            headers=headers,
            json=child_payload() | {"login": {"account_id": account.json()["id"]}},
        )
        assert created.status_code == 201, created.text
        assert client.get("/api/auth/accounts").json()[1]["member_id"] == created.json()["id"]


def test_account_from_another_family_cannot_be_taken_over_and_parent_role_is_protected(environment):
    app, registry, _, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        me = login(client, "Sertl")
        headers = {"x-csrf-token": me["csrf_token"]}
        payload = child_payload() | {
            "login": {"email": "henning@example.invalid", "password": "new-password-123"}
        }
        assert client.post("/api/members", headers=headers, json=payload).status_code == 409
        assert len(client.get("/api/members").json()) == 1
        assert (
            client.put(
                "/api/members/1",
                headers=headers,
                json={"name": "Parent", "role": "child", "color": "blue"},
            ).status_code
            == 409
        )
        assert client.get("/api/auth/me").json()["user"]["role"] == "parent"


def test_parent_reset_revokes_child_sessions_without_changing_parent_session(environment):
    app, _, _, _ = environment
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as parent:
        me = login(parent, "Sertl")
        headers = {"x-csrf-token": me["csrf_token"]}
        created = parent.post("/api/members", headers=headers, json=child_payload()).json()
        with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as child:
            assert child.post("/api/auth/login", json=child_payload()["login"]).status_code == 200
            payload = child_payload() | {
                "login": {"email": "tim@example.invalid", "password": "reset-password-123"}
            }
            response = parent.put(f"/api/members/{created['id']}", headers=headers, json=payload)
            assert response.status_code == 200, response.text
            assert child.get("/api/auth/me").status_code == 401
            assert parent.get("/api/auth/me").status_code == 200
            assert child.post("/api/auth/login", json=payload["login"]).status_code == 200


def test_failed_central_commit_never_activates_credentials_and_existing_profile_is_repairable(
    environment, monkeypatch
):
    from sqlalchemy import select

    from app.central_accounts import CentralAccountEditor

    app, registry, _, _ = environment
    original = CentralAccountEditor.commit_after_family
    failed = []

    def finalize(editor):
        if failed:
            return original(editor)
        failed.append(True)
        commit = editor.control.commit

        def reject():
            raise RuntimeError("Simulated auth DB commit failure")

        monkeypatch.setattr(editor.control, "commit", reject)
        try:
            return original(editor)
        finally:
            monkeypatch.setattr(editor.control, "commit", commit)

    monkeypatch.setattr(CentralAccountEditor, "commit_after_family", finalize)
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as parent:
        me = login(parent, "Sertl")
        headers = {"x-csrf-token": me["csrf_token"]}
        result = parent.post("/api/members", headers=headers, json=child_payload())
        assert result.status_code == 503
        assert result.json()["code"] == "auth.account_save_incomplete"
        with registry.session() as db:
            assert (
                db.scalar(select(Identity).where(Identity.email == "tim@example.invalid")) is None
            )
        profiles = parent.get("/api/members").json()
        child_id = next(member["id"] for member in profiles if member["name"] == "Tim")
        assert len(profiles) == 2
        result = parent.put(f"/api/members/{child_id}", headers=headers, json=child_payload())
        assert result.status_code == 200, result.text
        assert len(parent.get("/api/members").json()) == 2
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as child:
        assert child.post("/api/auth/login", json=child_payload()["login"]).status_code == 200
