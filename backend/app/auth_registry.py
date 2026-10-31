"""Future central identity registry, independent of family business tables.

These models are deliberately NOT part of app.db.Base or the legacy Alembic
metadata. No tables are created automatically in production.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db import NAMING_CONVENTION


class AuthBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Tenant(AuthBase):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    database_name: Mapped[str] = mapped_column(String(63), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="provisioning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Identity(AuthBase):
    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Only a central superadmin; family roles belong to memberships.
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(AuthBase):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("identity_id", "tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("identities.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    identity: Mapped[Identity] = relationship()
    tenant: Mapped[Tenant] = relationship()


class OAuthClient(AuthBase):
    """Registered public client; redirect URIs are exact-match only."""

    __tablename__ = "oauth_clients"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(default=False)


class OAuthAuthorizationCode(AuthBase):
    """Persist only the hash of the short-lived, single-use authorization code."""

    __tablename__ = "oauth_authorization_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("oauth_clients.id"))
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    code_challenge: Mapped[str] = mapped_column(String(43))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthGrant(AuthBase):
    """Revocable MCP authorization shared by rotated tokens."""

    __tablename__ = "oauth_grants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("oauth_clients.id"))
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    audience: Mapped[str] = mapped_column(String(2048))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthToken(AuthBase):
    """Opaque token digest; raw access and refresh secrets never persist."""

    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("oauth_grants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
