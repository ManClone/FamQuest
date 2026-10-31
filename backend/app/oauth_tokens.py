"""MCP token lifecycle, not yet exposed through HTTP or legacy MCP.

All mutations own their auth-DB transaction. In particular refresh-token reuse
must persist revocation even though the caller receives an authorization error.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_registry import OAuthClient, OAuthGrant, OAuthToken
from app.family_principal import FamilyPrincipal, resolve_family_principal
from app.oauth_codes import consume_code
from app.security import token_hash


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int = 600


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _principal(db: Session, grant: OAuthGrant) -> FamilyPrincipal:
    principal = resolve_family_principal(db, grant.identity_id)
    client = db.get(OAuthClient, grant.client_id)
    if (
        grant.revoked_at is not None
        or client is None
        or not client.enabled
        or principal.tenant_id != grant.tenant_id
        or principal.role not in {"admin", "parent"}
    ):
        raise PermissionError("MCP authorization revoked")
    return principal


def _issue_pair(db: Session, grant: OAuthGrant) -> TokenPair:
    pair = TokenPair(secrets.token_urlsafe(32), secrets.token_urlsafe(48))
    now = datetime.now(UTC)
    for kind, raw, lifetime in (
        ("access", pair.access_token, timedelta(seconds=pair.expires_in)),
        ("refresh", pair.refresh_token, timedelta(days=30)),
    ):
        db.add(
            OAuthToken(
                token_hash=token_hash(raw),
                grant_id=grant.id,
                kind=kind,
                expires_at=now + lifetime,
            )
        )
    return pair


def exchange_code(
    db: Session, *, code: str, client_id: str, redirect_uri: str, verifier: str, audience: str
) -> TokenPair:
    """Audience is configured by the server, never copied from untrusted input."""
    if not audience.startswith("https://"):
        raise ValueError("An HTTPS MCP audience is required")
    with db.begin():
        identity_id, tenant_id = consume_code(
            db, code=code, client_id=client_id, redirect_uri=redirect_uri, verifier=verifier
        )
        grant = OAuthGrant(
            id=secrets.token_hex(32),
            identity_id=identity_id,
            tenant_id=tenant_id,
            client_id=client_id,
            audience=audience,
        )
        _principal(db, grant)
        db.add(grant)
        db.flush()
        pair = _issue_pair(db, grant)
    return pair


def authenticate_access(db: Session, raw: str, *, audience: str) -> FamilyPrincipal:
    record = db.get(OAuthToken, token_hash(raw), populate_existing=True)
    if record is None or record.kind != "access" or _utc(record.expires_at) <= datetime.now(UTC):
        raise PermissionError("Invalid access token")
    grant = db.get(OAuthGrant, record.grant_id, populate_existing=True)
    if grant is None or not secrets.compare_digest(grant.audience, audience):
        raise PermissionError("Invalid MCP audience")
    # Refresh identity/membership state even if the caller previously loaded it.
    db.expire_all()
    return _principal(db, grant)


def rotate_refresh(db: Session, raw: str, *, client_id: str, audience: str) -> TokenPair:
    rejected = False
    with db.begin():
        # Lock the grant first: all refreshes in one token family serialize,
        # including concurrent replay of an ancestor refresh token.
        token = db.get(OAuthToken, token_hash(raw))
        if token is None or token.kind != "refresh":
            raise PermissionError("Invalid refresh token")
        grant = db.scalar(
            select(OAuthGrant)
            .where(OAuthGrant.id == token.grant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        db.refresh(token)
        if grant is None or grant.client_id != client_id or grant.audience != audience:
            raise PermissionError("Invalid refresh binding")
        _principal(db, grant)
        if token.consumed_at is not None:
            grant.revoked_at = datetime.now(UTC)
            rejected = True
        elif _utc(token.expires_at) <= datetime.now(UTC):
            raise PermissionError("Expired refresh token")
        else:
            token.consumed_at = datetime.now(UTC)
            pair = _issue_pair(db, grant)
    if rejected:
        raise PermissionError("Refresh reuse: grant revoked")
    return pair


def revoke_token(db: Session, raw: str, *, client_id: str) -> None:
    """Unknown tokens succeed without disclosing whether they existed."""
    with db.begin():
        token = db.get(OAuthToken, token_hash(raw))
        if token is None:
            return
        grant = db.scalar(
            select(OAuthGrant)
            .where(OAuthGrant.id == token.grant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if grant is not None and grant.client_id == client_id:
            grant.revoked_at = datetime.now(UTC)
