"""Stage inactive family records after their isolated databases are provisioned.

No PostgreSQL CREATE DATABASE is performed here. The caller owns the transaction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_registry import Tenant
from app.planned_families import ADDITIONAL_FAMILIES


def stage_planned_families(auth: Session) -> int:
    """Register Sertl and Henning as disabled, never activate automatically."""
    existing = {tenant.database_name: tenant for tenant in auth.scalars(select(Tenant)).all()}
    for family in ADDITIONAL_FAMILIES:
        tenant = existing.get(family.database_name)
        if tenant is not None:
            if tenant.name != family.name:
                raise ValueError("Conflicting tenant database assignment")
            if tenant.status != "disabled":
                raise ValueError("Existing tenant must remain disabled")
            continue
        auth.add(
            Tenant(
                name=family.name,
                database_name=family.database_name,
                status="disabled",
            )
        )
    auth.flush()
    return len(ADDITIONAL_FAMILIES)
