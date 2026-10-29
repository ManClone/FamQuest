"""Family resolution tests: never trust a request-supplied family."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_registry import AuthBase, Identity, Membership, Tenant
from app.family_principal import resolve_family_principal


def test_family_resolution_requires_single_active_membership():
    engine = create_engine("sqlite://")
    AuthBase.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            session.add_all(
                [
                    Tenant(id=1, name="Sertl", database_name="famquest_sertl", status="active"),
                    Tenant(id=2, name="Henning", database_name="famquest_henning", status="disabled"),
                    Identity(id=10, email="parent@example.org", password_hash="hash"),
                    Identity(
                        id=11,
                        email="super@example.org",
                        password_hash="hash",
                        is_superadmin=True,
                    ),
                ]
            )
            session.flush()
            session.add(Membership(identity_id=10, tenant_id=1, role="parent"))
            session.flush()
            principal = resolve_family_principal(session, 10)
            assert (principal.tenant_id, principal.database_name, principal.role) == (
                1,
                "famquest_sertl",
                "parent",
            )
            with pytest.raises(PermissionError):
                resolve_family_principal(session, 11)
            with pytest.raises(PermissionError):
                resolve_family_principal(session, 999)
            session.add(Membership(identity_id=10, tenant_id=2, role="parent"))
            session.flush()
            with pytest.raises(PermissionError):
                resolve_family_principal(session, 10)
    finally:
        engine.dispose()


def test_disabled_family_cannot_be_accessed():
    engine = create_engine("sqlite://")
    AuthBase.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            session.add(Tenant(id=1, name="Henning", database_name="famquest_henning", status="disabled"))
            session.add(Identity(id=1, email="test@example.org", password_hash="hash"))
            session.flush()
            session.add(Membership(identity_id=1, tenant_id=1, role="admin"))
            session.flush()
            with pytest.raises(PermissionError, match="not active"):
                resolve_family_principal(session, 1)
    finally:
        engine.dispose()
