"""Explicit maintenance helper for one NEW production family slot, never startup."""

import argparse
import json
import os
import secrets
from pathlib import Path

from sqlalchemy import URL, create_engine, select, text
from sqlalchemy.orm import Session

from app.auth_db import AuthDatabase
from app.auth_registry import FamilyCreation, Tenant
from app.config import FamilyDatabaseCredentials, Settings
from app.deployment_check import migration_head
from app.family_creation import configured_slots, verify_empty_slot
from app.family_slots import private_copy
from app.staging_bootstrap import _migrate
from app.tenant_provisioner import provision_empty_family
from app.tenant_provisioning import validate_family_database_name


def check_registry(settings, name):
    registry = AuthDatabase(settings)
    try:
        with registry.session() as db:
            root = Path(__file__).resolve().parents[1]
            if db.scalars(text("SELECT version_num FROM alembic_version")).all() != [
                migration_head(root / "auth_alembic")
            ]:
                raise ValueError("Auth migration differs; no existing schema will be migrated")
            if db.scalar(select(Tenant.id).where(Tenant.database_name == name)):
                raise ValueError("Database is already registered")
            if db.scalar(select(FamilyCreation.id).where(FamilyCreation.status == "provisioning")):
                raise ValueError("A family creation is in progress")
    finally:
        registry.close()


def prepare(
    path,
    name,
    admin_url,
    *,
    expected_host="live-db",
    expected_origin="https://famquest.websiteclone.de",
):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected a regular private runtime.json")
    validate_family_database_name(name)
    original = path.read_bytes()
    values = json.loads(original)
    if not isinstance(values, dict) or any(
        not isinstance(key, str) or key != key.upper() or not isinstance(value, str)
        for key, value in values.items()
    ):
        raise ValueError("Expected unambiguous string environment values")
    # Explicit values win over the helper's separately supplied admin environment.
    settings_values = {key.lower(): value for key, value in values.items()}
    for key in (
        "family_database_credentials",
        "auth_database_credentials",
        "family_creation_databases",
    ):
        if key in settings_values:
            settings_values[key] = json.loads(settings_values[key])
    settings = Settings(_env_file=None, **settings_values)
    if settings.postgres_host != expected_host or settings.public_url != expected_origin:
        raise ValueError("Unexpected production host or origin")
    if admin_url.host != settings.postgres_host or admin_url.port != settings.postgres_port:
        raise ValueError("Owner and runtime must use the same PostgreSQL server")
    configured_slots(settings)
    if name in settings.family_database_credentials or name in settings.family_creation_databases:
        raise ValueError("Slot already configured; no automatic retry")
    check_registry(settings, name)
    backup = path.with_name(f"runtime.before-{name}.json")
    staged = path.with_name(f"runtime.pending-{name}.json")
    if backup.exists() or staged.exists():
        raise ValueError("Previous maintenance exists; inspect before retrying")
    owner = (path.stat().st_uid, path.stat().st_gid)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with admin.connect() as conn:
            # Shared PostgreSQL advisory lock, also across independent helper containers.
            if not conn.scalar(text("SELECT pg_try_advisory_lock(731944216)")):
                raise ValueError("Another slot-maintenance helper is running")
            try:
                exists = conn.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name) "
                        "OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"
                    ),
                    {"name": name, "role": f"{name}_app"},
                )
                if exists:
                    raise ValueError("Database or role exists; never overwrite")
                if path.read_bytes() != original:
                    raise ValueError("Runtime changed during preflight")
                private_copy(backup, original, owner)
                credentials = FamilyDatabaseCredentials(
                    username=f"{name}_app", password=secrets.token_hex(32)
                )
                provision_empty_family(admin, name, credentials.password)
                # Only the just-created database is migrated, using its own restricted role.
                engine = _migrate(settings, name, credentials)
                try:
                    with Session(engine) as db:
                        verify_empty_slot(db)
                finally:
                    engine.dispose()
                mapping = dict(settings.family_database_credentials)
                mapping[name] = credentials
                values["FAMILY_DATABASE_CREDENTIALS"] = json.dumps(
                    {key: value.model_dump() for key, value in mapping.items()}
                )
                values["FAMILY_CREATION_DATABASES"] = json.dumps(
                    [*settings.family_creation_databases, name]
                )
                private_copy(staged, (json.dumps(values, indent=2) + "\n").encode(), owner)
                if path.read_bytes() != original:
                    raise ValueError("Runtime changed; pending configuration retained for review")
                os.replace(staged, path)
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(731944216)"))
    finally:
        admin.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default="/live-config/runtime.json")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    try:
        # Supplied only to this maintenance container, never written into runtime.json.
        admin_url = URL.create(
            "postgresql+psycopg",
            host="live-db",
            port=5432,
            database="postgres",
            username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )
        prepare(args.runtime, args.database, admin_url)
    except Exception as exc:
        print(
            f"REFUSED/FAILED ({type(exc).__name__}); no credentials printed. "
            "Do not retry or delete anything; inspect partial state first."
        )
        raise SystemExit(1) from None
    print(
        "PASS: one empty family database prepared; existing databases unchanged. "
        "Restart live-app to load its new slot configuration."
    )


if __name__ == "__main__":
    main()
