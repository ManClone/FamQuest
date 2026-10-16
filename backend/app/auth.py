import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.logs import logger
from app.models import AuthSession, Family, FamilyMember, User
from app.schemas import FamilyOut, MeResponse, UserOut
from app.security import new_token, token_hash

SESSION_COOKIE = "famquest_session"
CSRF_HEADER = "X-CSRF-Token"
# Das Wanddisplay soll dauerhaft angemeldet bleiben; jede Nutzung verlängert die Session.
SESSION_LIFETIME = timedelta(days=365)
SESSION_REFRESH_INTERVAL = timedelta(hours=1)
# Wie lange der Elternbereich nach PIN-Eingabe offen bleibt (verlängert sich bei Nutzung).
PARENT_UNLOCK_DURATION = timedelta(minutes=5)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DbSession = Annotated[Session, Depends(get_db)]


def utcnow() -> datetime:
    return datetime.now(UTC)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_family(db: Session) -> Family:
    family = db.scalars(select(Family)).one_or_none()
    if family is None:
        raise ApiError(status.HTTP_409_CONFLICT, "setup.required")
    return family


def check_origin(request: Request) -> None:
    """CSRF-Schutz für Requests ohne Session (Setup, Login): nur von der eigenen Seite."""
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if origin and urlsplit(origin).netloc != host:
        # Häufige Ursache hinter einem Reverse Proxy: Er gibt den Host-Header nicht weiter.
        logger.warning(
            "Anfrage an %s abgelehnt: Origin %s passt nicht zum Host %s "
            "(Reverse Proxy muss den Host-Header weitergeben)",
            request.url.path,
            origin,
            host,
        )
        raise ApiError(status.HTTP_403_FORBIDDEN, "auth.csrf_failed")


def start_session(db: Session, request: Request, response: Response, user: User) -> AuthSession:
    token = new_token()
    now = utcnow()
    auth_session = AuthSession(
        token_hash=token_hash(token),
        user=user,
        csrf_token=new_token(),
        last_seen_at=now,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(auth_session)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return auth_session


def end_session(db: Session, response: Response, auth_session: AuthSession) -> None:
    db.delete(auth_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_session(request: Request, db: DbSession) -> AuthSession:
    """Angemeldete Session; bei schreibenden Requests zusätzlich mit CSRF-Prüfung."""
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        from app.config import get_settings
        from app.mcp_access import allowed

        secret = get_settings().mcp_service_token
        supplied = authorization.removeprefix("Bearer ")
        if len(secret) < 32 or not hmac.compare_digest(supplied.encode(), secret.encode()):
            raise ApiError(401, "auth.not_authenticated")
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
        raw_id = request.headers.get("x-famquest-parent-id", "")
        user = db.get(User, int(raw_id)) if raw_id.isdecimal() else None
        if user is None or user.role not in ("admin", "parent"):
            raise ApiError(403, "mcp.parent_required")
        logger.info("MCP parent=%s method=%s path=%s", user.id, request.method, request.url.path)
        # Transient principal: no reusable browser session, cookie or CSRF exemption for cookies.
        return AuthSession(user_id=user.id, user=user)

    token = request.cookies.get(SESSION_COOKIE)
    auth_session = (
        db.scalars(select(AuthSession).where(AuthSession.token_hash == token_hash(token))).first()
        if token
        else None
    )
    now = utcnow()
    if auth_session is None or auth_session.expires_at <= now:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "auth.not_authenticated")

    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent.encode(), auth_session.csrf_token.encode()):
            logger.warning(
                "Anfrage an %s abgelehnt: CSRF-Token fehlt oder falsch", request.url.path
            )
            raise ApiError(status.HTTP_403_FORBIDDEN, "auth.csrf_failed")

    if now - auth_session.last_seen_at >= SESSION_REFRESH_INTERVAL:
        auth_session.last_seen_at = now
        auth_session.expires_at = now + SESSION_LIFETIME
        db.commit()
    return auth_session


CurrentSession = Annotated[AuthSession, Depends(current_session)]


def is_parent_unlocked(auth_session: AuthSession, family: Family) -> bool:
    if not family.pin_enabled:
        return True
    until = auth_session.parent_unlocked_until
    return until is not None and until > utcnow()


def unlock_parent_area(auth_session: AuthSession) -> None:
    auth_session.parent_unlocked_until = utcnow() + PARENT_UNLOCK_DURATION


def parent_session(auth_session: CurrentSession, db: DbSession) -> AuthSession:
    """Session mit entsperrtem Elternbereich; jede Nutzung verlängert die Entsperrung."""
    if auth_session.user.role not in ("admin", "parent"):
        raise ApiError(status.HTTP_403_FORBIDDEN, "parent.locked")
    return auth_session


ParentSession = Annotated[AuthSession, Depends(parent_session)]


def me_response(db: Session, auth_session: AuthSession) -> MeResponse:
    family = get_family(db)
    user = auth_session.user
    return MeResponse(
        user=UserOut(email=user.email, role=user.role, language=user.language),
        family=FamilyOut(
            name=family.name,
            default_language=family.default_language,
            timezone=family.timezone,
            pin_enabled=family.pin_enabled,
        ),
        csrf_token=auth_session.csrf_token,
        member_id=db.scalar(select(FamilyMember.id).where(FamilyMember.user_id == user.id)),
        parent_unlocked=user.role in ("admin", "parent"),
    )


def child_member_id(db: Session, auth_session: AuthSession) -> int | None:
    """None for parents, the linked member for children, zero for unlinked children."""
    if auth_session.user.role != "child":
        return None
    return (
        db.scalar(select(FamilyMember.id).where(FamilyMember.user_id == auth_session.user_id)) or 0
    )


def ensure_member_access(db: Session, auth_session: AuthSession, member_id: int) -> None:
    own = child_member_id(db, auth_session)
    if own is not None and own != member_id:
        raise ApiError(403, "profile.own_only")
