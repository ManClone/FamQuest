"""PostgreSQL-only provisioning for explicitly approved, empty tenant databases.

Never call during app startup. The operator must provide a privileged admin
connection and independently generated role passwords. No existing database
or role is modified.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.tenant_provisioning import provisioning_sql, quoted_identifier


def provision_empty_family(admin_engine: Engine, database_name: str, role_password: str) -> None:
    """Create a tenant role and database; refuse partial or existing setups."""
    if admin_engine.dialect.name != "postgresql":
        raise ValueError("PostgreSQL is required")
    if len(role_password) < 32:
        raise ValueError("A strong independently generated password is required")
    role_name = f"{database_name}_app"
    statements = provisioning_sql(database_name, role_name)
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database_name},
        ).scalar()
        role_exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
            {"name": role_name},
        ).scalar()
        if exists or role_exists:
            raise ValueError("Tenant database or role already exists; refusing to overwrite")
        conn.exec_driver_sql(statements[0])
        try:
            conn.execute(
                text(f"ALTER ROLE {quoted_identifier(role_name)} PASSWORD :password"),
                {"password": role_password},
            )
            for statement in statements[1:]:
                conn.exec_driver_sql(statement)
        except Exception:
            # A created database is never dropped automatically; manual review
            # is required after any partial failure.
            raise
