"""Generate reviewed SQL for separate family database roles.

This module never connects to PostgreSQL and never executes SQL. Run generated
statements only with explicit operator approval and separately managed secrets.
"""

import re

from app.planned_families import ADDITIONAL_FAMILIES

SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def quoted_identifier(name: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(name):
        raise ValueError("Invalid PostgreSQL identifier")
    return f'"{name}"'


def provisioning_sql(database_name: str, role_name: str) -> tuple[str, ...]:
    """DDL to review, not execute. Role password must be set separately."""
    database = quoted_identifier(database_name)
    role = quoted_identifier(role_name)
    if not database_name.startswith("famquest_"):
        raise ValueError("Family database name must start with famquest_")
    if role_name != f"{database_name}_app":
        raise ValueError("Family role must match its database")
    return (
        f"CREATE ROLE {role} LOGIN NOINHERIT;",
        f"CREATE DATABASE {database} OWNER {role};",
        f"REVOKE CONNECT ON DATABASE {database} FROM PUBLIC;",
        f"GRANT CONNECT ON DATABASE {database} TO {role};",
    )


def planned_provisioning_sql() -> dict[str, tuple[str, ...]]:
    return {
        family.name: provisioning_sql(family.database_name, f"{family.database_name}_app")
        for family in ADDITIONAL_FAMILIES
    }
