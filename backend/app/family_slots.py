"""Explicit preparation of two NEW empty staging databases. Never run in the web app."""

import argparse
import json
import os
import secrets
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import FamilyDatabaseCredentials, Settings
from app.family_creation import verify_empty_slot
from app.staging_bootstrap import (
    DATABASES,
    SPARE_DATABASES,
    _migrate,
    check_ready,
    inspect_cluster,
    validated_inputs,
)
from app.tenant_provisioner import provision_empty_family


def read_config(path):
    values = dict(dotenv_values(path, interpolate=False))
    fields = {}
    for key, value in values.items():
        if key.lower() in Settings.model_fields:
            fields[key.lower()] = value
    for name in (
        "auth_database_credentials",
        "family_database_credentials",
        "family_creation_databases",
    ):
        if name in fields:
            fields[name] = json.loads(fields[name])
    return values, Settings(_env_file=None, **fields)


def private_copy(path, data, owner=None):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    if owner is not None and hasattr(os, "chown"):
        current = path.stat()
        if (current.st_uid, current.st_gid) != owner:
            os.chown(path, *owner)


def replace_settings(original, changes):
    lines = original.splitlines()
    for key, value in changes.items():
        indexes = [index for index, line in enumerate(lines) if line.startswith(key + "=")]
        if len(indexes) > 1:
            raise ValueError("Ambiguous environment file")
        if indexes:
            lines[indexes[0]] = f"{key}={value}"
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def prepare(directory):
    directory = Path(directory).resolve()
    runtime_path, bootstrap_path = directory / "runtime.env", directory / "bootstrap.env"
    _, runtime = read_config(runtime_path)
    bootstrap_values, settings = read_config(bootstrap_path)
    validated_inputs(settings, bootstrap_values)
    if (
        runtime.family_database_credentials != settings.family_database_credentials
        or runtime.auth_database_credentials != settings.auth_database_credentials
        or runtime.public_url != settings.public_url
        or runtime.postgres_host != settings.postgres_host
        or runtime.postgres_port != settings.postgres_port
    ):
        raise ValueError("Runtime and bootstrap settings disagree")
    if runtime.family_creation_databases != settings.family_creation_databases:
        raise ValueError("Creation slot settings disagree")
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            if (
                inspect_cluster(
                    connection,
                    settings.public_url,
                    (*DATABASES, *settings.family_creation_databases),
                )
                != "ready"
            ):
                raise ValueError("Only an already initialized isolated cluster may be extended")
        if set(settings.family_creation_databases) == set(SPARE_DATABASES):
            check_ready(settings)
            return "already-ready"
        if settings.family_creation_databases:
            raise ValueError("Partial slot configuration requires manual review")
        check_ready(settings)  # Requires the reviewed current auth migration first.
        backups = [
            path.with_name(path.name + ".before-family-create")
            for path in (runtime_path, bootstrap_path)
        ]
        if any(path.exists() for path in backups):
            raise ValueError("Existing configuration backups are never overwritten")
        originals = [path.read_bytes() for path in (runtime_path, bootstrap_path)]
        owners = [
            (path.stat().st_uid, path.stat().st_gid) for path in (runtime_path, bootstrap_path)
        ]
        for path, data, owner in zip(backups, originals, owners, strict=True):
            private_copy(path, data, owner)
        credentials = dict(settings.family_database_credentials)
        for name in SPARE_DATABASES:
            secret = secrets.token_hex(24)
            credentials[name] = FamilyDatabaseCredentials(username=f"{name}_app", password=secret)
            provision_empty_family(admin, name, secret)
            engine = _migrate(settings, name, credentials[name])
            try:
                with Session(engine) as db:
                    verify_empty_slot(db)
            finally:
                engine.dispose()
        changes = {
            "FAMILY_DATABASE_CREDENTIALS": json.dumps(
                {name: value.model_dump() for name, value in credentials.items()},
                separators=(",", ":"),
            ),
            "FAMILY_CREATION_DATABASES": json.dumps(list(SPARE_DATABASES)),
        }
        # Stage both private files before replacing either. A partial failure is
        # deliberately not retried automatically or repaired by deleting data.
        staged = []
        for path, data, owner in zip(
            (runtime_path, bootstrap_path), originals, owners, strict=True
        ):
            content = replace_settings(data.decode("utf-8"), changes)
            temporary = path.with_name(path.name + ".family-create-new")
            private_copy(temporary, content.encode("utf-8"), owner)
            staged.append((temporary, path))
        for temporary, path in staged:
            os.replace(temporary, path)
        return "prepared"
    finally:
        admin.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    try:
        status = prepare(args.config_dir)
    except Exception as exc:
        print(
            f"Staging family-slot preparation refused or failed ({type(exc).__name__}); "
            "no secrets printed. Review partial state manually."
        )
        raise SystemExit(1) from None
    print(f"Staging family slots {status}; existing family data and login credentials unchanged.")


if __name__ == "__main__":
    main()
