"""Security lifecycle checks independent of the legacy family database."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_registry import AuthBase, Identity, Membership, OAuthClient, OAuthToken, Tenant
from app.oauth_codes import issue_code
from app.oauth_pkce import s256_challenge
from app.oauth_tokens import authenticate_access, exchange_code, revoke_token, rotate_refresh

AUDIENCE = "https://family.example.invalid/mcp"
REDIRECT = "https://chat.example.invalid/callback"


@pytest.fixture
def registry():
    engine = create_engine("sqlite://")
    AuthBase.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Identity(id=1, email="parent@example.invalid", password_hash="unused"),
                Tenant(id=1, name="Sertl", database_name="famquest_sertl", status="active"),
                Tenant(id=2, name="Henning", database_name="famquest_henning", status="active"),
                OAuthClient(id="client", redirect_uri=REDIRECT, enabled=True),
            ]
        )
        db.flush()
        db.add(Membership(identity_id=1, tenant_id=1, role="parent"))
        db.commit()
        yield db
    engine.dispose()


def pair(db):
    code = issue_code(
        db,
        client_id="client",
        redirect_uri=REDIRECT,
        identity_id=1,
        tenant_id=1,
        code_challenge=s256_challenge("v" * 43),
    )
    db.commit()
    return exchange_code(
        db,
        code=code,
        client_id="client",
        redirect_uri=REDIRECT,
        verifier="v" * 43,
        audience=AUDIENCE,
    )


def test_access_bound_to_tenant_audience_and_token_kind(registry):
    tokens = pair(registry)
    assert authenticate_access(registry, tokens.access_token, audience=AUDIENCE).tenant_id == 1
    for raw, audience in (
        (tokens.access_token, "https://wrong.invalid/mcp"),
        (tokens.refresh_token, AUDIENCE),
        ("invented", AUDIENCE),
    ):
        with pytest.raises(PermissionError):
            authenticate_access(registry, raw, audience=audience)
    persisted = registry.scalars(select(OAuthToken.token_hash)).all()
    assert tokens.access_token not in persisted
    assert tokens.refresh_token not in persisted
    assert all(len(digest) == 64 for digest in persisted)


def test_refresh_replay_persists_revocation_for_all_descendants(registry):
    first = pair(registry)
    second = rotate_refresh(registry, first.refresh_token, client_id="client", audience=AUDIENCE)
    assert second.refresh_token != first.refresh_token
    with pytest.raises(PermissionError, match="reuse"):
        rotate_refresh(registry, first.refresh_token, client_id="client", audience=AUDIENCE)
    # The error must not roll back revocation.
    registry.expire_all()
    with pytest.raises(PermissionError):
        authenticate_access(registry, second.access_token, audience=AUDIENCE)
    registry.rollback()
    with pytest.raises(PermissionError):
        rotate_refresh(registry, second.refresh_token, client_id="client", audience=AUDIENCE)


@pytest.mark.parametrize("change", ["tenant", "membership", "client", "superadmin", "child"])
def test_authorization_changes_apply_to_existing_access_tokens(registry, change):
    tokens = pair(registry)
    if change == "tenant":
        registry.get(Tenant, 1).status = "disabled"
    elif change == "membership":
        registry.scalar(select(Membership)).tenant_id = 2
    elif change == "client":
        registry.get(OAuthClient, "client").enabled = False
    elif change == "superadmin":
        registry.get(Identity, 1).is_superadmin = True
    else:
        registry.scalar(select(Membership)).role = "child"
    registry.commit()
    with pytest.raises(PermissionError):
        authenticate_access(registry, tokens.access_token, audience=AUDIENCE)


def test_expired_access_is_rejected(registry):
    tokens = pair(registry)
    token = registry.scalar(select(OAuthToken).where(OAuthToken.kind == "access"))
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    registry.commit()
    with pytest.raises(PermissionError):
        authenticate_access(registry, tokens.access_token, audience=AUDIENCE)


def test_wrong_client_cannot_rotate_or_revoke(registry):
    tokens = pair(registry)
    with pytest.raises(PermissionError):
        rotate_refresh(registry, tokens.refresh_token, client_id="other", audience=AUDIENCE)
    revoke_token(registry, tokens.access_token, client_id="other")
    assert authenticate_access(registry, tokens.access_token, audience=AUDIENCE).tenant_id == 1
    registry.rollback()
    revoke_token(registry, tokens.refresh_token, client_id="client")
    with pytest.raises(PermissionError):
        authenticate_access(registry, tokens.access_token, audience=AUDIENCE)
