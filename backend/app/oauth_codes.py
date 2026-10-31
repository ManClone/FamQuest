"""Database-backed OAuth authorization code exchange primitives.

Not exposed as HTTP endpoints until authentication, migrations and access-token
issuance are implemented and tested.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_registry import Identity, Membership, OAuthAuthorizationCode, OAuthClient, Tenant
from app.oauth_pkce import verify_s256


def issue_code(
    db: Session,
    *,
    client_id: str,
    redirect_uri: str,
    identity_id: int,
    tenant_id: int,
    code_challenge: str,
) -> str:
    """Issue a short-lived code only for an active registered client/membership."""
    if not isinstance(code_challenge, str) or len(code_challenge) != 43:
        raise ValueError("Invalid challenge")
    # Challenge must be canonical base64url, not arbitrary 43-character text.
    import re

    if re.fullmatch(r"[A-Za-z0-9_-]{43}", code_challenge) is None:
        raise ValueError("Invalid challenge")
    client = db.get(OAuthClient, client_id)
    tenant = db.get(Tenant, tenant_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.identity_id == identity_id,
            Membership.tenant_id == tenant_id,
        )
    )
    identity = db.get(Identity, identity_id)
    if (
        client is None
        or not client.enabled
        or not secrets.compare_digest(client.redirect_uri, redirect_uri)
        or tenant is None
        or tenant.status != "active"
        or membership is None
        or membership.role not in {"admin", "parent"}
        or identity is None
        or identity.is_superadmin
    ):
        raise PermissionError("Authorization denied")
    code = secrets.token_urlsafe(32)
    db.add(
        OAuthAuthorizationCode(
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            client_id=client_id,
            identity_id=identity_id,
            tenant_id=tenant_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db.flush()
    return code


def consume_code(
    db: Session, *, code: str, client_id: str, redirect_uri: str, verifier: str
) -> tuple[int, int]:
    """Consume one code in a transaction; caller must commit before issuing tokens."""
    if not isinstance(code, str) or len(code) > 256:
        raise PermissionError("Invalid authorization code")
    digest = hashlib.sha256(code.encode()).hexdigest()
    record = db.scalar(
        select(OAuthAuthorizationCode)
        .where(OAuthAuthorizationCode.code_hash == digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    expires_at = record.expires_at if record is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        record is None
        or record.consumed_at is not None
        or expires_at <= now
        or not secrets.compare_digest(record.client_id, client_id)
        or not secrets.compare_digest(record.redirect_uri, redirect_uri)
        or not verify_s256(verifier, record.code_challenge, "S256")
    ):
        raise PermissionError("Invalid authorization code")
    client = db.get(OAuthClient, record.client_id)
    tenant = db.get(Tenant, record.tenant_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.identity_id == record.identity_id,
            Membership.tenant_id == record.tenant_id,
        )
    )
    identity = db.get(Identity, record.identity_id)
    if (
        client is None
        or not client.enabled
        or tenant is None
        or tenant.status != "active"
        or membership is None
        or membership.role not in {"admin", "parent"}
        or identity is None
        or identity.is_superadmin
    ):
        raise PermissionError("Authorization revoked")
    record.consumed_at = now
    db.flush()
    return record.identity_id, record.tenant_id
