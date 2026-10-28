"""Central auth registry tests; no live database needed."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.auth_registry import AuthBase, Identity, Membership, Tenant


def test_auth_registry_is_separate_from_legacy_metadata():
    from app.db import Base

    assert AuthBase.metadata is not Base.metadata
    assert set(AuthBase.metadata.tables) == {"tenants", "identities", "memberships"}
    assert not set(AuthBase.metadata.tables).intersection(Base.metadata.tables)


def test_tenant_database_name_is_unique():
    sql = str(CreateTable(Tenant.__table__).compile(dialect=postgresql.dialect()))
    assert "UNIQUE (database_name)" in sql


def test_membership_has_unique_identity_tenant_pair():
    sql = str(CreateTable(Membership.__table__).compile(dialect=postgresql.dialect()))
    assert "UNIQUE (identity_id, tenant_id)" in sql


def test_superadmin_does_not_require_family_membership():
    identity = Identity(email="root@example.org", password_hash="hash", is_superadmin=True)
    assert identity.is_superadmin is True
    assert not hasattr(identity, "tenant_id")
