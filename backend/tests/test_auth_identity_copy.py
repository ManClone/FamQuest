"""Identity copy tests using separate in-memory source and destination databases."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_identity_copy import stage_identity_copy
from app.auth_registry import AuthBase, Identity, Membership, Tenant
from app.db import engine as source_engine
from app.models import Family, User


def test_copy_keeps_ids_hashes_and_roles_without_modifying_source():
    destination_engine = create_engine("sqlite://")
    AuthBase.metadata.create_all(destination_engine)
    try:
        with Session(source_engine) as source:
            source.add(Family(id=1, name="Grasser", default_language="de"))
            source.add(
                User(
                    id=42,
                    email="test@example.org",
                    password_hash="existing-hash",
                    family_id=1,
                    role="parent",
                )
            )
            source.commit()
            with Session(destination_engine) as destination:
                assert stage_identity_copy(source, destination, "famquest_grasser") == 1
                destination.commit()
                identity = destination.get(Identity, 42)
                assert identity.email == "test@example.org"
                assert identity.password_hash == "existing-hash"
                assert identity.is_superadmin is False
                assert destination.get(Tenant, 1).status == "disabled"
                membership = destination.scalar(select(Membership))
                assert membership.family_user_id == 42
                assert (membership.identity_id, membership.tenant_id, membership.role) == (
                    42,
                    1,
                    "parent",
                )
            assert source.get(User, 42).password_hash == "existing-hash"
    finally:
        destination_engine.dispose()
