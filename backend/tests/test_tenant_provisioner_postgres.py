"""Exercise isolated database provisioning on the CI PostgreSQL service."""

from uuid import uuid4

from sqlalchemy import create_engine, text

from app.config import Settings
from app.tenant_provisioner import provision_empty_family
from app.tenant_provisioning import quoted_identifier


def test_provision_new_family_database_and_reject_duplicate():
    database_name = f"famquest_ci_{uuid4().hex[:12]}"
    role_name = f"{database_name}_app"
    admin = create_engine(Settings().database_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        provision_empty_family(admin, database_name, "test-only-secret-" + "x" * 32)
        with admin.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname=:name"),
                    {"name": database_name},
                ).scalar()
                == 1
            )
            assert (
                conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname=:name"),
                    {"name": role_name},
                ).scalar()
                == 1
            )

        import pytest

        with pytest.raises(ValueError, match="already exists"):
            provision_empty_family(admin, database_name, "test-only-secret-" + "x" * 32)
    finally:
        with admin.connect() as conn:
            conn.exec_driver_sql(
                f"DROP DATABASE IF EXISTS {quoted_identifier(database_name)} WITH (FORCE)"
            )
            conn.exec_driver_sql(f"DROP ROLE IF EXISTS {quoted_identifier(role_name)}")
        admin.dispose()
