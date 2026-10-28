from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import (
    CurrentSession,
    DbSession,
    ParentSession,
    check_origin,
    client_ip,
    end_session,
    me_response,
    start_session,
)
from app.demo_mode import NotInDemo
from app.errors import ApiError
from app.logs import logger
from app.models import Family, FamilyMember, User
from app.schemas import Email, MeResponse, Password
from app.security import hash_secret, login_limiter, needs_rehash, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: Email
    password: str


@router.post("/login", dependencies=[Depends(check_origin)])
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> MeResponse:
    limit_keys = (f"ip:{client_ip(request)}", f"email:{body.email}")
    if login_limiter.is_blocked(*limit_keys):
        logger.warning("Anmeldung gesperrt: zu viele Fehlversuche (von %s)", client_ip(request))
        raise ApiError(status.HTTP_429_TOO_MANY_REQUESTS, "auth.rate_limited")

    user = db.scalars(select(User).where(User.email == body.email)).one_or_none()
    if not verify_secret(user.password_hash if user else None, body.password):
        login_limiter.record_failure(*limit_keys)
        logger.warning(
            "Anmeldung fehlgeschlagen: %s (von %s)",
            f"falsches Passwort für Konto {user.id}" if user else "kein Konto mit dieser E-Mail",
            client_ip(request),
        )
        logger.debug("Fehlgeschlagene Anmeldung mit E-Mail %r", body.email)
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "auth.invalid_credentials")

    assert user is not None
    login_limiter.reset(f"email:{body.email}")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_secret(body.password)
    auth_session = start_session(db, request, response, user)
    db.commit()
    logger.info("Anmeldung: Konto %s (von %s)", user.id, client_ip(request))
    return me_response(db, auth_session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth_session: CurrentSession, response: Response, db: DbSession) -> None:
    end_session(db, response, auth_session)
    db.commit()
    logger.info("Abmeldung: Konto %s", auth_session.user_id)


@router.get("/me")
def me(auth_session: CurrentSession, db: DbSession) -> MeResponse:
    return me_response(db, auth_session)


class AccountCreateRequest(BaseModel):
    email: Email
    password: Password
    role: str


class AccountOut(BaseModel):
    id: int
    email: str
    role: str
    member_id: int | None = None


@router.get("/accounts", dependencies=[NotInDemo])
def list_accounts(auth: ParentSession, db: DbSession) -> list[AccountOut]:
    family_id = auth.user.family_id
    if family_id is None:
        family_id = db.scalar(select(Family.id))
    if family_id is None:
        raise ApiError(status.HTTP_409_CONFLICT, "setup.required")
    links = dict(
        db.execute(
            select(FamilyMember.user_id, FamilyMember.id).where(FamilyMember.user_id.is_not(None))
        ).all()
    )
    return [
        AccountOut(id=user.id, email=user.email, role=user.role, member_id=links.get(user.id))
        for user in db.scalars(
            select(User).where(User.family_id == family_id).order_by(User.id)
        )
    ]


@router.post("/accounts", status_code=status.HTTP_201_CREATED, dependencies=[NotInDemo])
def create_account(body: AccountCreateRequest, auth: ParentSession, db: DbSession) -> AccountOut:
    if body.role not in ("parent", "child"):
        raise ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, "auth.invalid_role")
    family_id = auth.user.family_id
    if family_id is None:
        family_id = db.scalar(select(Family.id))
    if family_id is None:
        raise ApiError(status.HTTP_409_CONFLICT, "setup.required")
    user = User(
        email=body.email,
        password_hash=hash_secret(body.password),
        role=body.role,
        family_id=family_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(status.HTTP_409_CONFLICT, "auth.email_taken") from exc
    logger.info("Konto %s mit Rolle %s erstellt", user.id, user.role)
    return AccountOut(id=user.id, email=user.email, role=user.role)
