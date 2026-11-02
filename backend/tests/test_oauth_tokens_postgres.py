"""Exercise real PostgreSQL locking; SQLite cannot verify concurrent replay."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_registry import BrowserSession, Identity, Membership, OAuthClient, Tenant
from app.browser_sessions import change_browser_password, login_browser
from app.config import Settings
from app.oauth_codes import consume_code, issue_code
from app.oauth_pkce import s256_challenge
from app.oauth_tokens import authenticate_access, rotate_refresh
from app.security import hash_secret, verify_secret
from tests.test_oauth_tokens import AUDIENCE, REDIRECT, pair


@pytest.fixture
def auth_engine():
    name = f"famquest_oauth_ci_{uuid4().hex[:12]}"
    settings = Settings()
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(settings.database_url(name))
    try:
        config = Config(Path(__file__).resolve().parents[1] / "auth_alembic.ini")
        config.attributes["database_url"] = settings.database_url(name)
        command.upgrade(config, "head")
        with Session(engine) as db:
            db.add_all(
                [
                    Identity(id=1, email="parent@example.invalid", password_hash="unused"),
                    Tenant(id=1, name="Sertl", database_name="famquest_sertl", status="active"),
                    OAuthClient(id="client", redirect_uri=REDIRECT, enabled=True),
                ]
            )
            db.flush()
            db.add(Membership(identity_id=1, tenant_id=1, role="parent"))
            db.commit()
        yield engine
        command.downgrade(config, "base")
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def test_code_consumed_once_under_concurrent_exchange(auth_engine):
    with Session(auth_engine) as db:
        code = issue_code(
            db,
            client_id="client",
            redirect_uri=REDIRECT,
            identity_id=1,
            tenant_id=1,
            code_challenge=s256_challenge("v" * 43),
        )
        db.commit()

    def consume(_):
        with Session(auth_engine) as db:
            try:
                consume_code(
                    db, code=code, client_id="client", redirect_uri=REDIRECT, verifier="v" * 43
                )
                db.commit()
                return True
            except PermissionError:
                return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(consume, range(4))).count(True) == 1


def test_refresh_replay_revokes_concurrent_winner(auth_engine):
    with Session(auth_engine) as db:
        original = pair(db)

    def refresh(_):
        with Session(auth_engine) as db:
            try:
                return rotate_refresh(
                    db, original.refresh_token, client_id="client", audience=AUDIENCE
                )
            except PermissionError:
                return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        winners = [result for result in pool.map(refresh, range(4)) if result is not None]
    assert len(winners) == 1
    with Session(auth_engine) as db, pytest.raises(PermissionError):
        authenticate_access(db, winners[0].access_token, audience=AUDIENCE)


def test_concurrent_password_changes_revoke_all_sessions_once(auth_engine):
    from sqlalchemy import select

    password = "old-test-password-123"
    with Session(auth_engine) as db:
        db.get(Identity, 1).password_hash = hash_secret(password)
        db.commit()
        credentials = []
        for _ in range(2):
            raw, session = login_browser(db, "parent@example.invalid", password)
            credentials.append((raw, session.csrf_token))
            db.commit()

    def change(credential):
        raw, csrf = credential
        with Session(auth_engine) as db:
            try:
                change_browser_password(db, raw, csrf, password, "new-test-password-123")
                db.commit()
                return True
            except PermissionError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(change, credentials)).count(True) == 1
    with Session(auth_engine) as db:
        assert db.scalar(select(BrowserSession)) is None
        assert verify_secret(db.get(Identity, 1).password_hash, "new-test-password-123")


def test_copied_registry_ids_do_not_break_later_account_creation(auth_engine):
    from app.auth_identity_copy import align_registry_sequences

    with Session(auth_engine) as db:
        db.add(Identity(id=42, email="copied@example.invalid", password_hash="unused"))
        db.add(Tenant(id=20, name="Copied", database_name="famquest_copied", status="disabled"))
        db.flush()
        align_registry_sequences(db)
        account = Identity(email="next@example.invalid", password_hash="unused")
        family = Tenant(name="Next", database_name="famquest_next", status="disabled")
        db.add_all([account, family])
        db.flush()
        assert account.id == 43
        assert family.id == 21
