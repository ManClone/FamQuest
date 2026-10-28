"""Regression tests for the non-disruptive first step toward family ownership."""

import sqlalchemy as sa
from alembic import command

from app.db import SessionLocal
from tests.conftest import alembic_config, csrf, run_setup


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


def test_new_parent_created_account_is_assigned_to_family(client, parent):
    response = client.post(
        "/api/auth/accounts",
        json={"email": "second@example.org", "password": "test-password-123", "role": "parent"},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        family_id = db.scalar(sa.text("SELECT id FROM families"))
        account_family_id = db.scalar(
            sa.text("SELECT family_id FROM users WHERE email='second@example.org'")
        )
        assert account_family_id == family_id


def test_new_member_login_is_assigned_to_family(client, parent):
    response = client.post(
        "/api/members",
        json={
            "name": "Tim",
            "role": "child",
            "color": "green",
            "login": {"email": "tim@example.org", "password": "test-password-123"},
        },
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        family_id = db.scalar(sa.text("SELECT id FROM families"))
        account_family_id = db.scalar(
            sa.text("SELECT family_id FROM users WHERE email='tim@example.org'")
        )
        assert account_family_id == family_id


def test_account_directory_does_not_expose_unassigned_accounts(client, parent):
    with SessionLocal() as db:
        db.execute(
            sa.text(
                "INSERT INTO users (email, password_hash, role, family_id) "
                "VALUES ('unassigned@example.org', 'hash', 'parent', NULL)"
            )
        )
        db.commit()

    response = client.get("/api/auth/accounts")
    assert response.status_code == 200, response.text
    emails = {account["email"] for account in response.json()}
    assert "unassigned@example.org" not in emails
    assert parent["user"]["email"] in emails
