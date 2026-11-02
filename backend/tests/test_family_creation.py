from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.auth_registry import FamilyCreation, Identity, Membership, Tenant
from app.config import FamilyDatabaseCredentials, Settings
from app.family_creation import CreationRequest, SlotNotEmpty, configured_slots
from app.multitenant_app import create_app
from app.operator_setup import create_operator, migrate_creation_registry
from app.security import verify_secret
from tests.test_operator_console import NoFamilyAccess, Registry

PASSWORD = "new-independent-parent-password"


@pytest.fixture
def creation_setup(monkeypatch):
    registry = Registry()
    with registry.session() as db:
        create_operator(db, "operator@example.test", PASSWORD)
        db.commit()
    settings = Settings(
        _env_file=None,
        public_url="https://creation.example.test",
        family_creation_databases=["famquest_slot_c"],
        family_database_credentials={
            "famquest_slot_c": FamilyDatabaseCredentials(
                username="famquest_slot_c_app", password="c" * 48
            )
        },
    )
    calls = []

    def seed(router, tenant_id, name, request):
        calls.append((tenant_id, name, request.family_name))
        with registry.session() as db:
            assert db.get(Tenant, tenant_id).status == "provisioning"
        return 1

    monkeypatch.setattr("app.family_creation.seed_family", seed)
    app = create_app(settings, database=registry, family_router=NoFamilyAccess())
    with TestClient(
        app, base_url=settings.public_url, headers={"origin": settings.public_url}
    ) as client:
        response = client.post(
            "/operator/api/login", json={"email": "operator@example.test", "password": PASSWORD}
        )
        assert response.status_code == 200
        yield client, registry, {"x-csrf-token": response.json()["csrf_token"]}, calls, settings
    registry.engine.dispose()


def payload(**extra):
    return {
        "request_key": str(uuid4()),
        "family_name": "New family",
        "parent_name": "New parent",
        "parent_email": "parent-new@example.test",
        "password": PASSWORD,
        "language": "de",
        "timezone": "Europe/Berlin",
        "confirmed": True,
        **extra,
    }


def test_creation_reserves_dedicated_slot_and_parent_only_after_seed(creation_setup):
    client, registry, headers, calls, _ = creation_setup
    assert client.get("/operator/api/capabilities").json()["family_creation_capacity"] == 1
    request = payload()
    response = client.post("/operator/api/family-creations", json=request, headers=headers)
    assert response.status_code == 201 and response.json()["status"] == "ready"
    assert len(calls) == 1 and calls[0][1] == "famquest_slot_c"
    assert PASSWORD not in response.text and "password_hash" not in response.text
    with registry.session() as db:
        parent = db.scalar(select(Identity).where(Identity.email == request["parent_email"]))
        assert not parent.is_superadmin and verify_secret(parent.password_hash, PASSWORD)
        membership = db.scalar(select(Membership).where(Membership.identity_id == parent.id))
        assert membership.role == "parent" and membership.family_user_id == 1
        assert db.get(Tenant, membership.tenant_id).status == "active"
        assert "password" not in FamilyCreation.__table__.columns
    assert client.get("/operator/api/capabilities").json()["family_creation_capacity"] == 0
    jobs = client.get("/operator/api/family-creations").json()
    assert len(jobs) == 1 and jobs[0]["actor_email"] == "operator@example.test"


def test_replay_never_reseeds_or_changes_password_and_conflicts_are_rejected(creation_setup):
    client, registry, headers, calls, _ = creation_setup
    request = payload()
    first = client.post("/operator/api/family-creations", json=request, headers=headers).json()
    second = client.post(
        "/operator/api/family-creations",
        json={**request, "password": "a-different-long-password"},
        headers=headers,
    )
    assert second.json() == first and len(calls) == 1
    assert (
        client.post(
            "/operator/api/family-creations",
            json={**request, "family_name": "different"},
            headers=headers,
        ).status_code
        == 409
    )
    with registry.session() as db:
        parent = db.scalar(select(Identity).where(Identity.email == request["parent_email"]))
        assert verify_secret(parent.password_hash, PASSWORD)
    assert (
        client.post(
            "/operator/api/family-creations",
            json=payload(parent_email="second@example.test"),
            headers=headers,
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"confirmed": False},
        {"password": "short"},
        {"family_name": "  "},
        {"parent_name": " "},
        {"parent_name": "invalid\u0000name"},
        {"timezone": "invalid/timezone"},
        {"database_name": "postgres"},
        {"role": "superadmin"},
        {"actor_identity_id": 99},
        {"parent_email": "not-an-email"},
    ],
)
def test_creation_rejects_invalid_or_untrusted_fields(creation_setup, extra):
    client, registry, headers, calls, _ = creation_setup
    assert (
        client.post(
            "/operator/api/family-creations", json=payload(**extra), headers=headers
        ).status_code
        == 422
    )
    assert calls == []
    with registry.session() as db:
        assert list(db.scalars(select(FamilyCreation))) == []


def test_existing_identity_is_never_promoted_or_overwritten_and_csrf_is_required(creation_setup):
    client, registry, headers, calls, _ = creation_setup
    assert client.post("/operator/api/family-creations", json=payload()).status_code == 403
    assert (
        client.post(
            "/operator/api/family-creations",
            json=payload(parent_email="operator@example.test"),
            headers=headers,
        ).status_code
        == 409
    )
    assert calls == []
    with registry.session() as db:
        assert db.scalar(select(Identity)).is_superadmin


def test_failed_seed_is_visible_reserved_and_never_retried(creation_setup, monkeypatch):
    client, registry, headers, _, _ = creation_setup
    calls = []

    def fail(*args):
        calls.append(1)
        raise SlotNotEmpty("private-existing-data-must-not-be-disclosed")

    monkeypatch.setattr("app.family_creation.seed_family", fail)
    request = payload()
    result = client.post("/operator/api/family-creations", json=request, headers=headers)
    assert result.json()["status"] == "failed" and result.json()["error_code"] == "slot_not_empty"
    assert "private-existing-data" not in result.text
    assert (
        client.post("/operator/api/family-creations", json=request, headers=headers).json()
        == result.json()
    )
    assert calls == [1]
    with registry.session() as db:
        assert db.scalar(select(Tenant)).status == "provisioning_failed"
        assert list(db.scalars(select(Membership))) == []
    assert client.get("/operator/api/capabilities").json()["family_creation_capacity"] == 0


def test_operator_authority_loss_before_activation_leaves_family_inactive(
    creation_setup, monkeypatch
):
    client, registry, headers, _, _ = creation_setup

    def seed(*args):
        with registry.session() as db:
            db.scalar(
                select(Identity).where(Identity.is_superadmin.is_(True))
            ).is_superadmin = False
            db.commit()
        return 1

    monkeypatch.setattr("app.family_creation.seed_family", seed)
    assert (
        client.post("/operator/api/family-creations", json=payload(), headers=headers).json()[
            "status"
        ]
        == "failed"
    )
    with registry.session() as db:
        assert db.scalar(select(Tenant)).status != "active"
        assert list(db.scalars(select(Membership))) == []


def test_creation_requires_operator_cookie(creation_setup):
    client, _, _, _, _ = creation_setup
    client.cookies.clear()
    assert client.get("/operator/api/family-creations").status_code == 401
    assert client.get("/operator/api/capabilities").status_code == 401
    assert client.post("/operator/api/family-creations", json=payload()).status_code == 401


def test_slot_configuration_is_explicit_and_request_repr_redacts_password():
    assert configured_slots(Settings(_env_file=None)) == []
    with pytest.raises(ValueError):
        configured_slots(Settings(_env_file=None, family_creation_databases=["famquest_auth"]))
    with pytest.raises(ValueError):
        configured_slots(Settings(_env_file=None, family_creation_databases=["famquest_new"]))
    assert PASSWORD not in repr(CreationRequest.model_validate(payload()))


def test_creation_migration_preserves_existing_registry(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'creation.sqlite'}")
    config = Config(Path(__file__).resolve().parents[1] / "auth_alembic.ini")
    config.attributes["database_url"] = engine.url
    command.upgrade(config, "g20261101_status")
    try:
        with Session(engine) as db:
            db.add(
                Identity(
                    id=1,
                    email="operator@example.test",
                    password_hash="unchanged",
                    is_superadmin=True,
                )
            )
            db.add(
                Tenant(id=1, name="Existing", database_name="famquest_existing", status="active")
            )
            db.commit()
        registry = type("Registry", (), {"engine": engine})()
        migrate_creation_registry(registry)
        migrate_creation_registry(registry)
        with Session(engine) as db:
            assert db.get(Identity, 1).password_hash == "unchanged"
            assert db.get(Tenant, 1).name == "Existing"
            assert list(db.scalars(select(FamilyCreation))) == []
            db.execute(text("UPDATE alembic_version SET version_num='unknown'"))
            db.commit()
        with pytest.raises(ValueError):
            migrate_creation_registry(registry)
    finally:
        engine.dispose()
