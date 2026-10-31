"""Central browser identity checks. Caller owns the auth-DB transaction."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth_registry import BrowserSession, Identity, OAuthAuthorizationCode, OAuthGrant
from app.family_principal import FamilyPrincipal, resolve_family_principal
from app.security import hash_secret, needs_rehash, new_token, token_hash, verify_secret

COOKIE_NAME = "__Host-famquest_central"
SESSION_LIFETIME = timedelta(days=365)


class BrowserCsrfError(PermissionError):
    pass


def login_browser(db: Session, email: str, password: str) -> tuple[str, BrowserSession]:
    # Same lock order as password changes: identity before session. A login
    # using an old password cannot commit after a password change revokes sessions.
    identity = db.scalar(
        select(Identity)
        .where(Identity.email == email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not verify_secret(identity.password_hash if identity else None, password):
        raise PermissionError("Invalid credentials")
    assert identity is not None
    principal = resolve_family_principal(db, identity.id)
    if needs_rehash(identity.password_hash):
        identity.password_hash = hash_secret(password)
    raw = new_token()
    session = BrowserSession(
        token_hash=token_hash(raw),
        identity_id=identity.id,
        tenant_id=principal.tenant_id,
        csrf_token=new_token(),
        expires_at=datetime.now(UTC) + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    return raw, session


def authenticate_browser(
    db: Session, raw: str | None, *, csrf_token: str | None = None, writing: bool = False
) -> tuple[BrowserSession, FamilyPrincipal]:
    if not raw or len(raw) > 256:
        raise PermissionError("Invalid session")
    # A session may have been revoked since the caller last loaded it.
    db.expire_all()
    session = db.get(BrowserSession, token_hash(raw), populate_existing=True)
    if session is None:
        raise PermissionError("Invalid session")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise PermissionError("Expired session")
    principal = resolve_family_principal(db, session.identity_id)
    if principal.tenant_id != session.tenant_id:
        raise PermissionError("Session family changed")
    if writing and (
        not csrf_token
        or not secrets.compare_digest(csrf_token.encode(), session.csrf_token.encode())
    ):
        raise BrowserCsrfError("Invalid CSRF token")
    return session, principal


def change_browser_password(
    db: Session, raw: str, csrf_token: str, current_password: str, new_password: str
) -> None:
    session, principal = authenticate_browser(db, raw, csrf_token=csrf_token, writing=True)
    identity = db.scalar(
        select(Identity)
        .where(Identity.id == principal.identity_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # Recheck session after acquiring the identity lock: another password
    # change could have completed while this transaction was waiting.
    authenticate_browser(db, raw, csrf_token=csrf_token, writing=True)
    if not verify_secret(identity.password_hash, current_password):
        raise PermissionError("Invalid credentials")
    if len(new_password) < 10 or len(new_password) > 256:
        raise ValueError("Invalid password length")
    identity.password_hash = hash_secret(new_password)
    db.execute(delete(BrowserSession).where(BrowserSession.identity_id == identity.id))
    db.execute(
        update(OAuthAuthorizationCode)
        .where(OAuthAuthorizationCode.identity_id == identity.id)
        .values(consumed_at=datetime.now(UTC))
    )
    # A password change also revokes existing connector authorizations.
    db.execute(
        update(OAuthGrant)
        .where(OAuthGrant.identity_id == identity.id)
        .values(revoked_at=datetime.now(UTC))
    )
