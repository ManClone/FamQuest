"""Actual PostgreSQL races: suspend vs credential issuance and duplicate actions."""

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth_registry import BrowserSession, Identity, OAuthGrant, Tenant, TenantStatusEvent
from app.browser_sessions import login_browser
from app.errors import ApiError
from app.oauth_codes import issue_code
from app.oauth_pkce import s256_challenge
from app.oauth_tokens import exchange_code
from app.security import hash_secret
from app.tenant_status import StatusChange, change_status
from tests.test_oauth_tokens import AUDIENCE, REDIRECT
from tests.test_oauth_tokens_postgres import auth_engine as auth_engine

PASSWORD = "test-only-status-password"


def change_request():
    return StatusChange(
        expected_status="active",
        status="disabled",
        family_name="Sertl",
        reason="Concurrency test",
        confirmed=True,
        request_key=uuid4(),
    )


def seed_operator(engine):
    with Session(engine) as db:
        db.get(Identity, 1).password_hash = hash_secret(PASSWORD)
        db.add(
            Identity(
                id=2, email="operator@example.invalid", password_hash="unused", is_superadmin=True
            )
        )
        db.commit()


@pytest.mark.parametrize("identical", [True, False])
def test_parallel_operator_requests_make_one_status_event(auth_engine, identical):
    seed_operator(auth_engine)
    request = change_request()

    def worker(_):
        with Session(auth_engine) as db:
            try:
                event = change_status(db, 2, 1, request if identical else change_request())
                db.commit()
                return event.id
            except ApiError as exc:
                db.rollback()
                return exc.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))
    with Session(auth_engine) as db:
        events = list(db.scalars(select(TenantStatusEvent)))
        assert len(events) == 1 and db.get(Tenant, 1).status == "disabled"
        if identical:
            assert results == [events[0].id] * 4
        else:
            assert results.count(409) == 3


@pytest.mark.parametrize("mode", ["browser", "authorization_code", "exchange"])
def test_suspension_wins_against_waiting_credential_issuance(auth_engine, mode):
    seed_operator(auth_engine)
    code = None
    if mode == "exchange":
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
    pids = Queue()

    def worker():
        # Pin the connection: a commit must not swap the observed backend PID.
        with auth_engine.connect() as connection, Session(bind=connection) as db:
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            connection.commit()
            pids.put(pid)
            try:
                if mode == "browser":
                    login_browser(db, "parent@example.invalid", PASSWORD)
                    db.commit()
                elif mode == "authorization_code":
                    issue_code(
                        db,
                        client_id="client",
                        redirect_uri=REDIRECT,
                        identity_id=1,
                        tenant_id=1,
                        code_challenge=s256_challenge("v" * 43),
                    )
                    db.commit()
                else:
                    exchange_code(
                        db,
                        code=code,
                        client_id="client",
                        redirect_uri=REDIRECT,
                        verifier="v" * 43,
                        audience=AUDIENCE,
                    )
                return "unexpectedly-issued"
            except PermissionError:
                db.rollback()
                return "denied"

    with Session(auth_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.scalar(select(Tenant).where(Tenant.id == 1).with_for_update())
        future = pool.submit(worker)
        try:
            pid = pids.get(timeout=5)
            waiting = False
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                with auth_engine.connect() as observer:
                    waiting = observer.scalar(
                        text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                        {"pid": pid},
                    )
                if waiting:
                    break
                time.sleep(0.02)
            assert waiting, "The credential issuer must wait on the tenant lock"
            change_status(blocker, 2, 1, change_request())
            blocker.commit()
        finally:
            # Always release the row before joining the worker, even on assertion failure.
            blocker.rollback()
        assert future.result(timeout=10) == "denied"
    with Session(auth_engine) as db:
        assert db.get(Tenant, 1).status == "disabled"
        assert list(db.scalars(select(BrowserSession))) == []
        assert list(db.scalars(select(OAuthGrant))) == []
