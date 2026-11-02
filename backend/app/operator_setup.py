"""Explicit operator setup. Never run on startup; never promote an existing account."""

import argparse
from getpass import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.auth_db import AuthDatabase
from app.auth_registry import Identity
from app.config import Settings
from app.deployment_check import migration_head
from app.schemas import Email
from app.security import hash_secret


def create_operator(db, email, password):
    from pydantic import TypeAdapter

    email = TypeAdapter(Email).validate_python(email)
    if not 16 <= len(password) <= 128:
        raise ValueError("Use a separate operator password of 16 to 128 characters")
    if db.scalar(select(Identity.id).where(Identity.email == email)) is not None:
        raise ValueError("Existing accounts are never promoted or overwritten")
    identity = Identity(email=email, password_hash=hash_secret(password), is_superadmin=True)
    db.add(identity)
    db.flush()
    return identity


def migrate_registry(registry):
    # Explicitly limited to the additive operator migration, never a future head.
    with registry.engine.connect() as connection:
        current = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    if current not in (["e20261031_actors"], ["f20261101_operator"]):
        raise ValueError("Unexpected registry revision; manual review required")
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "auth_alembic.ini")
    config.attributes.update(database_url=registry.engine.url, configure_logger=False)
    command.upgrade(config, "f20261101_operator")


def migrate_status_registry(registry):
    with registry.engine.connect() as connection:
        current = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    if current not in (["f20261101_operator"], ["g20261101_status"]):
        raise ValueError("Unexpected registry revision; manual review required")
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "auth_alembic.ini")
    config.attributes.update(database_url=registry.engine.url, configure_logger=False)
    command.upgrade(config, "g20261101_status")


def migrate_creation_registry(registry):
    with registry.engine.connect() as connection:
        current = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    if current not in (["g20261101_status"], ["h20261102_creation"]):
        raise ValueError("Unexpected registry revision; manual review required")
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "auth_alembic.ini")
    config.attributes.update(database_url=registry.engine.url, configure_logger=False)
    command.upgrade(config, "h20261102_creation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply-reviewed-auth-migration", action="store_true")
    mode.add_argument("--apply-reviewed-status-migration", action="store_true")
    mode.add_argument("--apply-reviewed-creation-migration", action="store_true")
    mode.add_argument("--email")
    args = parser.parse_args()
    registry = AuthDatabase(Settings())
    try:
        if args.apply_reviewed_creation_migration:
            migrate_creation_registry(registry)
            print(
                "Reviewed additive family-creation migration applied; no family database changed."
            )
            return
        if args.apply_reviewed_status_migration:
            migrate_status_registry(registry)
            print("Reviewed additive status-audit migration applied; no family database changed.")
            return
        if args.apply_reviewed_auth_migration:
            migrate_registry(registry)
            print(
                "Reviewed additive operator-session migration applied; no family database changed."
            )
            return
        root = Path(__file__).resolve().parents[1]
        with registry.session() as db:
            if db.scalars(text("SELECT version_num FROM alembic_version")).all() != [
                migration_head(root / "auth_alembic")
            ]:
                raise ValueError("Apply the reviewed registry migration first")
            password = getpass("New independent operator password (16+ characters): ")
            if password != getpass("Repeat operator password: "):
                raise ValueError("Passwords differ")
            create_operator(db, args.email, password)
            db.commit()
        print("Separate operator created; no family membership or existing account changed.")
    except Exception as exc:
        print(f"Operator setup refused or failed ({type(exc).__name__}); no credentials printed.")
        raise SystemExit(1) from None
    finally:
        registry.close()


if __name__ == "__main__":
    main()
