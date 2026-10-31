"""Integrated staging app: central authentication selects every business DB.

Not selected by the production entrypoint yet. OAuth HTTP, write deduplication
and per-family schedulers remain explicit release gates.
"""

from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import auth
from app.api import (
    approvals,
    calendar,
    calendar_week,
    chores,
    event_symbols,
    frame,
    home,
    maintenance,
    meals,
    members,
    money,
    parent,
    photos,
    points,
    profile,
    rewards,
    routines,
    shopping,
    task_week,
    tasks,
    today,
    todos,
    weather,
    weekly_consequences,
)
from app.api.auth import AccountCreateRequest, AccountOut
from app.auth_db import AuthDatabase
from app.auth_registry import Identity, Membership
from app.browser_sessions import COOKIE_NAME, BrowserCsrfError, authenticate_browser
from app.central_accounts import editor_for
from app.central_auth import create_app as create_login_app
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.family_db import FamilyDatabase, FamilyDatabaseRouter
from app.family_principal import FamilyPrincipal
from app.mcp_access import allowed, tool_schema
from app.models import AuthSession, Family, FamilyMember, User
from app.oauth_tokens import authenticate_access
from app.tenant_storage import tenant_upload_root


def local_actor(db: Session, principal: FamilyPrincipal) -> User:
    if principal.family_user_id is None:
        raise ApiError(403, "auth.family_mapping_required")
    local = db.get(User, principal.family_user_id)
    family = db.scalars(select(Family)).one_or_none()
    if (
        local is None
        or family is None
        or local.family_id != family.id
        or local.role != principal.role
    ):
        raise ApiError(403, "auth.family_mapping_required")
    # Business audit IDs stay local; credentials are never read from this row.
    return User(
        id=local.id,
        family_id=family.id,
        email=principal.email,
        role=principal.role,
        language=local.language,
        password_hash="!",
    )


def create_app(
    settings: Settings | None = None,
    *,
    database: AuthDatabase | None = None,
    family_router: FamilyDatabaseRouter | None = None,
):
    settings = settings or get_settings()
    if settings.demo_mode:
        raise ValueError("Demo mode cannot be combined with central family routing")
    registry = database or AuthDatabase(settings)
    router = family_router or FamilyDatabaseRouter(settings)

    def family_session(principal):
        return router.session(FamilyDatabase(principal.tenant_id, principal.database_name))

    def render_me(auth_db, browser_session, principal):
        with family_session(principal) as db:
            user = local_actor(db, principal)
            return auth.me_response(
                db, AuthSession(user_id=user.id, user=user, csrf_token=browser_session.csrf_token)
            )

    app = create_login_app(
        settings, database=registry, session_renderer=render_me, allow_mcp_bearer=True
    )
    app.state.auth_registry = registry
    app.state.family_router = router
    app.state.multitenant = True
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original_lifespan(application):
                yield
        finally:
            if family_router is None:
                router.close()
            if database is None:
                registry.close()

    app.router.lifespan_context = lifespan

    def resolve_request(request: Request):
        with registry.session() as db:
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                principal = authenticate_access(
                    db, authorization[7:], audience=settings.public_url.rstrip("/") + "/mcp"
                )
                if not allowed(request.method, request.url.path):
                    raise ApiError(403, "mcp.operation_forbidden")
                if (
                    request.method != "GET"
                    and (
                        "approvals/" in request.url.path
                        or request.url.path.endswith(("/revoke", "/reverse"))
                    )
                    and request.headers.get("x-mcp-parent-confirmed") != "true"
                ):
                    raise ApiError(409, "mcp.parent_confirmation_required")
                if request.method != "GET":
                    # Enable only after central gateway write deduplication is integrated.
                    raise ApiError(503, "mcp.central_gateway_required")
                return principal, ""
            session, principal = authenticate_browser(
                db,
                request.cookies.get(COOKIE_NAME),
                csrf_token=request.headers.get("x-csrf-token"),
                writing=request.method not in auth.SAFE_METHODS,
            )
            return principal, session.csrf_token

    @app.middleware("http")
    async def bind_family(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in {
            "/api/auth/login",
            "/api/auth/me",
            "/api/auth/logout",
            "/api/auth/password",
            "/api/health",
            "/api/setup/status",
        }:
            return await call_next(request)
        try:
            principal, csrf = await run_in_threadpool(resolve_request, request)
        except BrowserCsrfError:
            return JSONResponse({"code": "auth.csrf_failed"}, status_code=403)
        except PermissionError:
            return JSONResponse({"code": "auth.not_authenticated"}, status_code=401)
        except ApiError as exc:
            return JSONResponse({"code": exc.code}, status_code=exc.status_code)
        request.state.family_principal = principal
        request.state.central_csrf = csrf
        if path.startswith("/api/calendar/google/"):
            return JSONResponse({"code": "calendar.central_oauth_required"}, status_code=503)
        storage = settings.upload_dir / "families" / str(principal.tenant_id)
        token = tenant_upload_root.set(storage)
        try:
            return await call_next(request)
        finally:
            tenant_upload_root.reset(token)

    def get_family_db(request: Request) -> Iterator[Session]:
        principal = getattr(request.state, "family_principal", None)
        if principal is None:
            raise ApiError(401, "auth.not_authenticated")
        with family_session(principal) as db:
            local_actor(db, principal)
            with registry.session() as control:
                db.info["central_control"] = control
                db.info["family_principal"] = principal
                yield db

    def current_family_session(request: Request, db: auth.DbSession):
        user = local_actor(db, request.state.family_principal)
        return AuthSession(user=user, user_id=user.id, csrf_token=request.state.central_csrf)

    app.dependency_overrides[get_db] = get_family_db
    app.dependency_overrides[auth.current_session] = current_family_session

    @app.get("/api/auth/accounts")
    def accounts(actor: auth.ParentSession, db: auth.DbSession) -> list[AccountOut]:
        control = db.info["central_control"]
        principal = db.info["family_principal"]
        links = dict(
            db.execute(
                select(FamilyMember.user_id, FamilyMember.id).where(
                    FamilyMember.user_id.is_not(None)
                )
            ).all()
        )
        result = []
        for mapping, identity in control.execute(
            select(Membership, Identity)
            .join(Identity, Identity.id == Membership.identity_id)
            .where(Membership.tenant_id == principal.tenant_id)
            .order_by(Membership.family_user_id)
        ):
            user = (
                db.get(User, mapping.family_user_id) if mapping.family_user_id is not None else None
            )
            if (
                user is not None
                and user.family_id == actor.user.family_id
                and not identity.is_superadmin
            ):
                result.append(
                    AccountOut(
                        id=user.id,
                        email=identity.email,
                        role=mapping.role,
                        member_id=links.get(user.id),
                    )
                )
        return result

    @app.post("/api/auth/accounts", status_code=201)
    def create_account(
        body: AccountCreateRequest, actor: auth.ParentSession, db: auth.DbSession
    ) -> AccountOut:
        editor = editor_for(db)
        user = editor.create_unlinked(body.email, body.password, body.role, actor.user.family_id)
        account_id = user.id
        members.commit_member(db)
        return AccountOut(id=account_id, email=body.email, role=body.role)

    @app.get("/api/setup/status")
    def setup_status():
        return {"setup_required": False, "demo": None}

    filtered = APIRouter()
    for module in (
        maintenance,
        parent,
        members,
        task_week,
        tasks,
        today,
        points,
        profile,
        money,
        weekly_consequences,
        rewards,
        approvals,
        calendar,
        calendar_week,
        event_symbols,
        weather,
        home,
        routines,
        photos,
        frame,
        meals,
        shopping,
        chores,
        todos,
    ):
        for route in module.router.routes:
            if getattr(route, "path", "") != "/profile/password":
                filtered.routes.append(route)
    app.include_router(filtered, prefix="/api")

    password_route = next(
        route for route in app.routes if getattr(route, "path", "") == "/api/auth/password"
    )
    app.add_api_route(
        "/api/profile/password", password_route.endpoint, methods=["PUT"], status_code=204
    )

    @app.get("/api/internal/mcp/schema", include_in_schema=False)
    def mcp_schema(_: auth.ParentSession):
        return tool_schema(app.openapi())

    return app
