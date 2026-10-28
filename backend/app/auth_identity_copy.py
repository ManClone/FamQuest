"""One-time, non-destructive copy of legacy logins to the auth registry.

Only use on a restored source backup and a freshly provisioned destination.
The caller owns the destination transaction; this function never commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_migration_inventory import assert_single_family_migration_ready, inspect_legacy
from app.auth_registry import Identity, Membership, Tenant
from app.models import Family, User


def stage_identity_copy(source: Session, destination: Session, database_name: str) -> int:
    assert_single_family_migration_ready(inspect_legacy(source))
    if destination.scalar(select(Tenant.id).limit(1)) is not None:
        raise ValueError("Auth registry is not empty")
    if destination.scalar(select(Identity.id).limit(1)) is not None:
        raise ValueError("Auth identities are not empty")
    if destination.scalar(select(Membership.id).limit(1)) is not None:
        raise ValueError("Auth memberships are not empty")
    if database_name != "famquest_grasser":
        raise ValueError("Expected explicitly approved Grasser test database")

    family = source.scalars(select(Family)).one()
    users = source.scalars(select(User).order_by(User.id)).all()
    if any(user.family_id != family.id for user in users):
        raise ValueError("Legacy user ownership mismatch")

    destination.add(
        Tenant(
            id=family.id,
            name=family.name,
            database_name=database_name,
            status="disabled",
        )
    )
    for user in users:
        destination.add(
            Identity(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                is_superadmin=False,
                created_at=user.created_at,
            )
        )
        destination.add(Membership(identity_id=user.id, tenant_id=family.id, role=user.role))
    destination.flush()
    return len(users)
