"""Explicit, audited status changes. Caller owns the registry transaction."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, update

from app.auth_registry import (
    BrowserSession,
    OAuthAuthorizationCode,
    OAuthGrant,
    Tenant,
    TenantStatusEvent,
)
from app.errors import ApiError


class StatusChange(BaseModel):
    model_config = {"extra": "forbid"}
    expected_status: Literal["active", "disabled"]
    status: Literal["active", "disabled"]
    family_name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    confirmed: Literal[True]
    request_key: UUID

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if not value.strip():
            raise ValueError("A reason is required")
        return value.strip()


def change_status(db, actor_id, tenant_id, body):
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if tenant is None:
        raise ApiError(404, "common.not_found")
    existing = db.scalar(
        select(TenantStatusEvent).where(
            TenantStatusEvent.actor_identity_id == actor_id,
            TenantStatusEvent.request_key == str(body.request_key),
        )
    )
    if existing:
        if (
            existing.tenant_id,
            existing.family_name,
            existing.from_status,
            existing.to_status,
            existing.reason,
        ) != (tenant_id, body.family_name, body.expected_status, body.status, body.reason):
            raise ApiError(409, "auth.operator_conflict")
        return existing
    if body.family_name != tenant.name:
        raise ApiError(409, "auth.operator_confirmation_failed")
    if tenant.status not in {"active", "disabled"}:
        raise ApiError(409, "auth.operator_status_unavailable")
    if tenant.status != body.expected_status or tenant.status == body.status:
        raise ApiError(409, "auth.operator_conflict")
    event = TenantStatusEvent(
        tenant_id=tenant.id,
        actor_identity_id=actor_id,
        request_key=str(body.request_key),
        family_name=tenant.name,
        from_status=tenant.status,
        to_status=body.status,
        reason=body.reason,
    )
    tenant.status = body.status
    db.add(event)
    if body.status == "disabled":
        now = datetime.now(UTC)
        # Lock order: tenant -> codes -> grants. Issuance takes the same tenant
        # lock before creating sessions/codes/grants, preventing late credentials.
        db.execute(delete(BrowserSession).where(BrowserSession.tenant_id == tenant.id))
        db.execute(
            update(OAuthAuthorizationCode)
            .where(
                OAuthAuthorizationCode.tenant_id == tenant.id,
                OAuthAuthorizationCode.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        db.execute(
            update(OAuthGrant)
            .where(OAuthGrant.tenant_id == tenant.id, OAuthGrant.revoked_at.is_(None))
            .values(revoked_at=now)
        )
    db.flush()
    return event
