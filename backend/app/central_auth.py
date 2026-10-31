"""Staging-only central login service. Not mounted by the legacy application.

No automatic schema creation, provisioning or family-data access occurs here.
The auth database must be migrated explicitly before this service is used.
"""

from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth_db import AuthDatabase
from app.auth_registry import Identity, Tenant
from app.browser_sessions import (
    COOKIE_NAME,
    SESSION_LIFETIME,
    BrowserCsrfError,
    authenticate_browser,
    change_browser_password,
    login_browser,
)
from app.config import Settings, get_settings
from app.errors import ApiError, register_error_handlers
from app.schemas import Email, Password
from app.security import RateLimiter


class LoginIn(BaseModel):
    model_config = {"extra": "forbid"}
    email: Email
    password: str = Field(max_length=256)


class PasswordIn(BaseModel):
    model_config = {"extra": "forbid"}
    current_password: str = Field(max_length=256)
    new_password: Password


class SessionOut(BaseModel):
    email: str
    role: str
    family_name: str
    csrf_token: str


def create_app(
    settings: Settings | None = None,
    *,
    database: AuthDatabase | None = None,
    session_renderer: Callable | None = None,
    allow_mcp_bearer: bool = False,
) -> FastAPI:
    settings = settings or get_settings()
    parsed = urlsplit(settings.public_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Central auth requires a configured HTTPS origin")
    origin = f"https://{parsed.netloc}"
    registry = database or AuthDatabase(settings)
    limiter = RateLimiter(max_failures=5, window_seconds=900)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if database is None:
            registry.close()

    app = FastAPI(
        title="FamQuest central login (staging)", lifespan=lifespan, docs_url=None, openapi_url=None
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def browser_boundary(request: Request, call_next):
        from fastapi.responses import JSONResponse

        # Only the configured host/origin can set or use these browser cookies.
        if str(request.url).split("/", 3)[:3] != origin.split("/", 3)[:3]:
            return JSONResponse({"code": "auth.csrf_failed"}, status_code=403)
        from app.mcp_access import allowed

        mcp_request = (
            allow_mcp_bearer
            and request.headers.get("authorization", "").startswith("Bearer ")
            and allowed(request.method, request.url.path)
        )
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("origin") != origin
            and not mcp_request
        ):
            return JSONResponse({"code": "auth.csrf_failed"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def get_registry() -> Iterator[Session]:
        with registry.session() as db:
            yield db

    Db = Annotated[Session, Depends(get_registry)]

    def current(request: Request, db: Session, *, writing: bool = False):
        try:
            return authenticate_browser(
                db,
                request.cookies.get(COOKIE_NAME),
                csrf_token=request.headers.get("x-csrf-token"),
                writing=writing,
            )
        except BrowserCsrfError as exc:
            raise ApiError(403, "auth.csrf_failed") from exc
        except PermissionError as exc:
            raise ApiError(401, "auth.not_authenticated") from exc

    def session_out(db: Session, session, principal) -> SessionOut:
        if session_renderer is not None:
            return session_renderer(db, session, principal)
        return SessionOut(
            email=db.get(Identity, principal.identity_id).email,
            role=principal.role,
            family_name=db.get(Tenant, principal.tenant_id).name,
            csrf_token=session.csrf_token,
        )

    @app.get("/api/health")
    def health(db: Db):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    @app.post("/api/auth/login", response_model=None)
    def login(body: LoginIn, request: Request, response: Response, db: Db) -> SessionOut:
        keys = (f"ip:{request.client.host if request.client else 'unknown'}", f"email:{body.email}")
        if limiter.is_blocked(*keys):
            raise ApiError(429, "auth.rate_limited")
        try:
            raw, session = login_browser(db, body.email, body.password)
            _, principal = authenticate_browser(db, raw)
            result = session_out(db, session, principal)
            db.commit()
        except PermissionError as exc:
            db.rollback()
            limiter.record_failure(*keys)
            raise ApiError(401, "auth.invalid_credentials") from exc
        limiter.reset(keys[1])
        response.set_cookie(
            COOKIE_NAME,
            raw,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/",
            max_age=int(SESSION_LIFETIME.total_seconds()),
        )
        return result

    @app.get("/api/auth/me", response_model=None)
    def me(request: Request, db: Db) -> SessionOut:
        session, principal = current(request, db)
        return session_out(db, session, principal)

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response, db: Db):
        session, _ = current(request, db, writing=True)
        db.delete(session)
        db.commit()
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")

    @app.put("/api/auth/password", status_code=204)
    def password(body: PasswordIn, request: Request, response: Response, db: Db):
        _, principal = current(request, db, writing=True)
        key = f"password:{principal.identity_id}"
        if limiter.is_blocked(key):
            raise ApiError(429, "auth.rate_limited")
        try:
            change_browser_password(
                db,
                request.cookies.get(COOKIE_NAME),
                request.headers.get("x-csrf-token"),
                body.current_password,
                body.new_password,
            )
            db.commit()
        except PermissionError as exc:
            db.rollback()
            limiter.record_failure(key)
            raise ApiError(403, "auth.invalid_credentials") from exc
        limiter.reset(key)
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")

    return app
