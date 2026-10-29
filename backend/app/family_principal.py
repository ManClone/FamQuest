"""Resolve family access exclusively from a verified central identity.

The caller must authenticate the identity first. Request headers, supplied
family IDs and database names must never select a family connection.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_registry import Identity, Membership, Tenant


@dataclass(frozen=True)
class FamilyPrincipal:
    identity_id: int
    tenant_id: int
    database_name: str
    role: str


def resolve_family_principal(auth: Session, identity_id: int) -> FamilyPrincipal:
    identity = auth.get(Identity, identity_id)
    if identity is None or identity.is_superadmin:
        raise PermissionError("No family access for this identity")

    memberships = auth.scalars(
        select(Membership).where(Membership.identity_id == identity_id)
    ).all()
    # No implicit default family: multi-family identities need an explicit,
    # separately authenticated family-selection mechanism in the future.
    if len(memberships) != 1:
        raise PermissionError("Exactly one active family membership is required")

    membership = memberships[0]
    tenant = auth.get(Tenant, membership.tenant_id)
    if tenant is None or tenant.status != "active":
        raise PermissionError("Family is not active")
    if membership.role not in {"admin", "parent", "child"}:
        raise PermissionError("Invalid family role")
    return FamilyPrincipal(
        identity_id=identity.id,
        tenant_id=tenant.id,
        database_name=tenant.database_name,
        role=membership.role,
    )
