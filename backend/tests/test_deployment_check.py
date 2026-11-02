"""Deployment readiness is read-only and refuses incomplete family configuration."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth_registry import Membership
from app.deployment_check import verify
from app.models import User
from tests import test_multitenant_app

environment = test_multitenant_app.environment


def versions(registry, router):
    engines = [registry.engine, *router.engines.values()]
    for engine in engines:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(text("INSERT INTO alembic_version VALUES ('expected')"))


def test_current_mapped_families_pass_without_modification(environment):
    _, registry, router, _ = environment
    versions(registry, router)
    assert verify(registry, router, auth_head="expected", family_head="expected") == [1, 2]
    with Session(router.engines["famquest_sertl"]) as db:
        assert db.get(User, 1).password_hash == "!"


def test_old_migration_is_refused_without_applying_it(environment):
    _, registry, router, _ = environment
    versions(registry, router)
    with pytest.raises(RuntimeError, match="explicit migration"):
        verify(registry, router, auth_head="expected", family_head="new")
    with Session(router.engines["famquest_sertl"]) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "expected"


def test_missing_mapping_and_family_local_passwords_are_release_gates(environment):
    _, registry, router, _ = environment
    versions(registry, router)
    with Session(router.engines["famquest_sertl"]) as db:
        db.get(User, 1).password_hash = "legacy-credential-hash"
        db.commit()
    with pytest.raises(RuntimeError, match="explicit removal"):
        verify(registry, router, auth_head="expected", family_head="expected")
    with Session(router.engines["famquest_sertl"]) as db:
        assert db.get(User, 1).password_hash == "legacy-credential-hash"
        db.get(User, 1).password_hash = "!"
        db.commit()
    with registry.session() as control:
        from sqlalchemy import select

        control.scalar(select(Membership).where(Membership.identity_id == 1)).family_user_id = None
        control.commit()
    from app.errors import ApiError

    with pytest.raises(ApiError):
        verify(registry, router, auth_head="expected", family_head="expected")


def test_all_disabled_families_can_restart_only_with_independent_operator(environment):
    from sqlalchemy import select

    from app.auth_registry import Identity, Tenant

    _, registry, router, _ = environment
    versions(registry, router)
    with registry.session() as control:
        for tenant in control.scalars(select(Tenant)):
            tenant.status = "disabled"
        control.commit()
    with pytest.raises(RuntimeError, match="No active family"):
        verify(registry, router, auth_head="expected", family_head="expected")
    with registry.session() as control:
        control.add(
            Identity(id=99, email="operator@example.invalid", password_hash="!", is_superadmin=True)
        )
        control.commit()

    class NoConnections:
        def session(self, family):
            raise AssertionError("Disabled family databases must not be opened")

    assert verify(registry, NoConnections(), auth_head="expected", family_head="expected") == []
