"""Isolated authorization-code lifecycle tests (no production database)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_registry import (
    AuthBase,
    Identity,
    Membership,
    OAuthClient,
    Tenant,
)
from app.oauth_codes import consume_code, issue_code
from app.oauth_pkce import s256_challenge


@pytest.fixture
def registry():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    AuthBase.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Tenant(id=1, name="Test", database_name="famquest_test", status="active"),
            Identity(id=1, email="test@example.invalid", password_hash="test"),
            OAuthClient(id="chatgpt-test", redirect_uri="https://example.invalid/callback", enabled=True),
        ])
        db.flush()
        db.add(Membership(identity_id=1, tenant_id=1, role="parent"))
        db.commit()
        yield db
    engine.dispose()


def test_code_is_single_use_and_bound_to_pkce(registry):
    verifier = "v" * 43
    code = issue_code(
        registry, client_id="chatgpt-test",
        redirect_uri="https://example.invalid/callback",
        identity_id=1, tenant_id=1,
        code_challenge=s256_challenge(verifier),
    )
    registry.commit()
    with pytest.raises(PermissionError):
        consume_code(
            registry, code=code, client_id="chatgpt-test",
            redirect_uri="https://example.invalid/callback", verifier="x" * 43,
        )
    assert consume_code(
        registry, code=code, client_id="chatgpt-test",
        redirect_uri="https://example.invalid/callback", verifier=verifier,
    ) == (1, 1)
    registry.commit()
    with pytest.raises(PermissionError):
        consume_code(
            registry, code=code, client_id="chatgpt-test",
            redirect_uri="https://example.invalid/callback", verifier=verifier,
        )


def test_code_denied_after_family_deactivation(registry):
    verifier = "v" * 43
    code = issue_code(
        registry, client_id="chatgpt-test",
        redirect_uri="https://example.invalid/callback",
        identity_id=1, tenant_id=1,
        code_challenge=s256_challenge(verifier),
    )
    registry.commit()
    registry.get(Tenant, 1).status = "disabled"
    registry.commit()
    with pytest.raises(PermissionError):
        consume_code(
            registry, code=code, client_id="chatgpt-test",
            redirect_uri="https://example.invalid/callback", verifier=verifier,
        )


def test_code_denied_after_client_revocation(registry):
    verifier = "v" * 43
    code = issue_code(
        registry, client_id="chatgpt-test",
        redirect_uri="https://example.invalid/callback",
        identity_id=1, tenant_id=1,
        code_challenge=s256_challenge(verifier),
    )
    registry.commit()
    registry.get(OAuthClient, "chatgpt-test").enabled = False
    registry.commit()
    with pytest.raises(PermissionError):
        consume_code(
            registry, code=code, client_id="chatgpt-test",
            redirect_uri="https://example.invalid/callback", verifier=verifier,
        )
