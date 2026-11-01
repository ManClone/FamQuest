"""Read-only operator console. Independent cookies, no family database access."""

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth_registry import Identity, Membership, OperatorSession, Tenant, TenantStatusEvent
from app.central_auth import LoginIn
from app.errors import ApiError
from app.security import (
    RateLimiter,
    hash_secret,
    needs_rehash,
    new_token,
    token_hash,
    verify_secret,
)
from app.tenant_status import StatusChange, change_status

COOKIE = "__Host-famquest_operator"
LIFETIME = timedelta(hours=1)


def authenticate(db, raw, csrf=None, *, writing=False):
    if not raw or len(raw) > 256:
        raise ApiError(401, "auth.not_authenticated")
    session = db.get(OperatorSession, token_hash(raw), populate_existing=True)
    if session is None:
        raise ApiError(401, "auth.not_authenticated")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    identity = db.get(Identity, session.identity_id, populate_existing=True)
    if expires <= datetime.now(UTC) or identity is None or not identity.is_superadmin:
        raise ApiError(401, "auth.not_authenticated")
    # Operator identities must remain independent of family accounts.
    if db.scalar(select(Membership.id).where(Membership.identity_id == identity.id).limit(1)):
        raise ApiError(403, "auth.operator_required")
    if writing and (
        not csrf or not secrets.compare_digest(csrf.encode(), session.csrf_token.encode())
    ):
        raise ApiError(403, "auth.csrf_failed")
    return session, identity


def install(app, registry):
    limiter = RateLimiter(max_failures=5, window_seconds=900)

    @app.get("/operator", response_class=HTMLResponse, include_in_schema=False)
    def page():
        response = HTMLResponse(
            Path(__file__).with_name("operator_console.html").read_text(encoding="utf-8")
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/operator/assets/{name}", include_in_schema=False)
    def asset(name: str):
        if name not in {"console.js", "console.css"}:
            raise ApiError(404, "common.not_found")
        content = Path(__file__).with_name("operator_" + name).read_text(encoding="utf-8")
        return Response(
            content, media_type="text/javascript" if name.endswith(".js") else "text/css"
        )

    @app.post("/operator/api/login", include_in_schema=False)
    def login(body: LoginIn, request: Request, response: Response):
        keys = (f"ip:{request.client.host if request.client else 'unknown'}", f"email:{body.email}")
        if limiter.is_blocked(*keys):
            raise ApiError(429, "auth.rate_limited")
        with registry.session() as db:
            identity = db.scalar(
                select(Identity).where(Identity.email == body.email).with_for_update()
            )
            valid = verify_secret(identity.password_hash if identity else None, body.password)
            if (
                not valid
                or identity is None
                or not identity.is_superadmin
                or db.scalar(
                    select(Membership.id).where(Membership.identity_id == identity.id).limit(1)
                )
            ):
                limiter.record_failure(*keys)
                raise ApiError(401, "auth.invalid_credentials")
            if needs_rehash(identity.password_hash):
                identity.password_hash = hash_secret(body.password)
            # Rotate this browser's previous operator session on successful login.
            previous = request.cookies.get(COOKIE)
            if previous and len(previous) <= 256:
                old = db.get(OperatorSession, token_hash(previous))
                if old:
                    db.delete(old)
            raw = new_token()
            session = OperatorSession(
                token_hash=token_hash(raw),
                identity_id=identity.id,
                csrf_token=new_token(),
                expires_at=datetime.now(UTC) + LIFETIME,
            )
            db.add(session)
            db.commit()
            limiter.reset(keys[1])
            response.set_cookie(
                COOKIE,
                raw,
                secure=True,
                httponly=True,
                samesite="strict",
                path="/",
                max_age=int(LIFETIME.total_seconds()),
            )
            return {"email": identity.email, "csrf_token": session.csrf_token}

    @app.get("/operator/api/session", include_in_schema=False)
    def me(request: Request):
        with registry.session() as db:
            session, identity = authenticate(db, request.cookies.get(COOKIE))
            return {"email": identity.email, "csrf_token": session.csrf_token}

    @app.get("/operator/api/families", include_in_schema=False)
    def families(request: Request):
        with registry.session() as db:
            authenticate(db, request.cookies.get(COOKIE))
            rows = db.execute(
                select(Tenant, func.count(Membership.id))
                .outerjoin(Membership, Membership.tenant_id == Tenant.id)
                .group_by(Tenant.id)
                .order_by(Tenant.name, Tenant.id)
            ).all()
            return [
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "status": tenant.status,
                    "accounts": count,
                    "created_at": tenant.created_at,
                }
                for tenant, count in rows
            ]

    @app.post("/operator/api/families/{tenant_id}/status", include_in_schema=False)
    def status(tenant_id: int, body: StatusChange, request: Request):
        with registry.session() as db:
            _, actor = authenticate(
                db, request.cookies.get(COOKIE), request.headers.get("x-csrf-token"), writing=True
            )
            try:
                event = change_status(db, actor.id, tenant_id, body)
                db.commit()
                return {"event_id": event.id, "status": event.to_status}
            except IntegrityError as exc:
                db.rollback()
                raise ApiError(409, "auth.operator_conflict") from exc

    @app.get("/operator/api/families/{tenant_id}/history", include_in_schema=False)
    def history(tenant_id: int, request: Request, before: int | None = Query(default=None, ge=1)):
        with registry.session() as db:
            authenticate(db, request.cookies.get(COOKIE))
            if db.get(Tenant, tenant_id) is None:
                raise ApiError(404, "common.not_found")
            query = (
                select(TenantStatusEvent, Identity.email)
                .join(Identity, Identity.id == TenantStatusEvent.actor_identity_id)
                .where(TenantStatusEvent.tenant_id == tenant_id)
            )
            if before is not None:
                query = query.where(TenantStatusEvent.id < before)
            rows = db.execute(query.order_by(TenantStatusEvent.id.desc()).limit(51)).all()
            items = [
                {
                    "id": event.id,
                    "family_name": event.family_name,
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "reason": event.reason,
                    "actor_email": email,
                    "created_at": event.created_at,
                }
                for event, email in rows[:50]
            ]
            return {"items": items, "next_before": items[-1]["id"] if len(rows) > 50 else None}

    @app.post("/operator/api/logout", status_code=204, include_in_schema=False)
    def logout(request: Request, response: Response):
        with registry.session() as db:
            session, _ = authenticate(
                db, request.cookies.get(COOKIE), request.headers.get("x-csrf-token"), writing=True
            )
            db.delete(session)
            db.commit()
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="strict", path="/")

    @app.api_route(
        "/operator/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown(path: str):
        raise ApiError(404, "common.not_found")
