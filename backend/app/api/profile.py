"""Self-service profile controls, separate from family administration."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.members import AvatarUpload, member_out, remove_avatar, upload_avatar
from app.auth import CurrentSession, DbSession
from app.demo_mode import NotInDemo
from app.errors import ApiError
from app.models import AuthSession, FamilyMember, User
from app.schemas import MemberName, MemberOut, Password
from app.security import hash_secret, login_limiter, verify_secret

router = APIRouter(prefix="/profile", tags=["profile"])


def own_member(auth: CurrentSession, db: DbSession) -> FamilyMember:
    member = db.scalar(select(FamilyMember).where(FamilyMember.user_id == auth.user_id))
    if member is None:
        raise ApiError(409, "profile.not_linked")
    return member


class ProfileOut(BaseModel):
    email: str
    member: MemberOut | None


class ProfileIn(BaseModel):
    model_config = {"extra": "forbid"}
    name: MemberName


class PasswordIn(BaseModel):
    model_config = {"extra": "forbid"}
    current_password: str
    new_password: Password


@router.get("")
def get_profile(auth: CurrentSession, db: DbSession) -> ProfileOut:
    member = db.scalar(select(FamilyMember).where(FamilyMember.user_id == auth.user_id))
    return ProfileOut(email=auth.user.email, member=member_out(member) if member else None)


@router.put("", dependencies=[NotInDemo])
def update_profile(body: ProfileIn, auth: CurrentSession, db: DbSession) -> ProfileOut:
    member = own_member(auth, db)
    member.name = body.name
    db.commit()
    return ProfileOut(email=auth.user.email, member=member_out(member))


@router.put("/password", status_code=204, dependencies=[NotInDemo])
def change_password(body: PasswordIn, auth: CurrentSession, db: DbSession) -> None:
    key = f"profile-password:{auth.user_id}"
    if login_limiter.is_blocked(key):
        raise ApiError(429, "auth.rate_limited")
    user = db.scalar(
        select(User)
        .where(User.id == auth.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not verify_secret(user.password_hash, body.current_password):
        login_limiter.record_failure(key)
        raise ApiError(403, "auth.invalid_credentials")
    login_limiter.reset(key)
    user.password_hash = hash_secret(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != auth.id))
    db.commit()


@router.put("/avatar", dependencies=[NotInDemo])
def set_avatar(auth: CurrentSession, db: DbSession, upload: AvatarUpload) -> MemberOut:
    return upload_avatar(own_member(auth, db).id, auth, db, upload)


@router.delete("/avatar", dependencies=[NotInDemo])
def clear_avatar(auth: CurrentSession, db: DbSession) -> MemberOut:
    return remove_avatar(own_member(auth, db).id, auth, db)
