"""Manage a person's login inside the same transaction as their profile."""

from fastapi import Request
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.demo_mode import forbid_in_demo
from app.errors import ApiError
from app.models import AuthSession, Family, FamilyMember, User
from app.schemas import MemberExistingLogin, MemberLoginCredentials
from app.security import hash_secret


def save_member_login(
    db: Session,
    member: FamilyMember,
    login: MemberLoginCredentials | MemberExistingLogin | None,
    auth: AuthSession,
    request: Request,
) -> None:
    if getattr(request.app.state, "multitenant", False):
        from app.central_accounts import editor_for

        editor_for(db).save_member(member, login, auth)
        return
    # Do not flush a changed profile until all account validation has passed.
    with db.no_autoflush:
        family_id = auth.user.family_id
        if family_id is None:
            family_id = db.scalar(select(Family.id))
        user = db.scalar(select(User).where(User.id == member.user_id).with_for_update())
        if isinstance(login, MemberExistingLogin):
            forbid_in_demo(request)
            if user is not None and user.id != login.account_id:
                raise ApiError(409, "auth.login_already_linked")
            user = db.scalar(select(User).where(User.id == login.account_id).with_for_update())
            if user is None or user.family_id not in (None, family_id):
                raise ApiError(404, "common.not_found")
            owner = db.scalar(select(FamilyMember.id).where(FamilyMember.user_id == user.id))
            if owner is not None and owner != member.id:
                raise ApiError(409, "auth.login_already_linked")
            if user.role != member.role and not (user.role == "admin" and member.role == "parent"):
                raise ApiError(409, "auth.login_role_mismatch")
            member.user_id = user.id
        elif isinstance(login, MemberLoginCredentials):
            forbid_in_demo(request)
            duplicate = db.scalar(select(User.id).where(User.email == login.email))
            if duplicate is not None and (user is None or duplicate != user.id):
                raise ApiError(409, "auth.email_taken")
            if user is None:
                if login.password is None:
                    raise ApiError(422, "auth.login_password_required")
                try:
                    user = db.scalar(
                        insert(User)
                        .values(
                            email=login.email,
                            password_hash=hash_secret(login.password),
                            role=member.role,
                            family_id=family_id,
                        )
                        .returning(User)
                    )
                except IntegrityError as exc:
                    db.rollback()
                    raise ApiError(409, "auth.email_taken") from exc
                assert user is not None
                member.user_id = user.id
            else:
                user.email = login.email
                if login.password is not None:
                    user.password_hash = hash_secret(login.password)
        if user is None:
            return
        if user.family_id not in (None, family_id):
            raise ApiError(404, "common.not_found")
        if user.family_id is None:
            user.family_id = family_id
        role_changed = user.role != member.role and user.role != "admin"
        if member.role == "child" and (user.role == "admin" or user.id == auth.user_id):
            raise ApiError(409, "auth.login_role_protected")
        if role_changed:
            forbid_in_demo(request)
            user.role = member.role
        if role_changed or (
            isinstance(login, MemberLoginCredentials) and login.password is not None
        ):
            db.execute(
                delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != auth.id)
            )
