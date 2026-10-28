"""Regression tests for the non-disruptive first step toward family ownership."""

import sqlalchemy as sa
from alembic import command

from app.db import SessionLocal
from tests.conftest import alembic_config, run_setup


def test_existing_users_are_backfilled_to_existing_family():
    config = alembic_config()
    command.downgrade(config, "j20261016dragon")
    with SessionLocal() as db:
        db.execute(
            sa.text(
                "INSERT INTO families (id, name, default_language) "
                "VALUES (1, 'Familie Grasser', 'de')"
            )
        )
        db.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, role) "
                "VALUES (1, 'parent@example.org', 'hash', 'admin')"
            )
        )
        db.commit()

    command.upgrade(config, "head")
    with SessionLocal() as db:
        assert db.scalar(sa.text("SELECT family_id FROM users WHERE id = 1")) == 1
        assert db.scalar(sa.text("SELECT count(*) FROM users")) == 1
        assert db.scalar(sa.text("SELECT count(*) FROM families")) == 1


def test_initial_admin_has_family_id(client):
    run_setup(client)
    with SessionLocal() as db:
        assert db.scalar(sa.text("SELECT family_id FROM users WHERE role = 'admin'")) == db.scalar(
            sa.text("SELECT id FROM families")
        )
