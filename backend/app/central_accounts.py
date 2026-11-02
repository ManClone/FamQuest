"""Family-local profiles with credentials stored exclusively in the auth DB.

The family transaction commits first. Only then may central credentials become
usable. If the second commit fails, report incomplete setup; a visible local
profile can be repaired by editing it. Never activate a central mapping before
its local actor exists, or compensate by deleting already committed profiles.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_registry import (
    BrowserSession,
    Identity,
    Membership,
    OAuthAuthorizationCode,
    OAuthGrant,
)
from app.errors import ApiError
from app.family_principal import FamilyPrincipal
from app.logs import logger
from app.models import FamilyMember, User
from app.schemas import MemberExistingLogin, MemberLoginCredentials
from app.security import hash_secret


class CentralAccountEditor:
    def __init__(self, family: Session, control: Session, principal: FamilyPrincipal) -> None:
        self.family = family
        self.control = control
        self.principal = principal

    def _mapping(self, local_id: int):
        mapping = self.control.scalar(
            select(Membership).where(
                Membership.tenant_id == self.principal.tenant_id,
                Membership.family_user_id == local_id,
            )
        )
        if mapping is None:
            return None, None
        identity = self.control.scalar(
            select(Identity)
            .where(Identity.id == mapping.identity_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        mapping = self.control.scalar(
            select(Membership)
            .where(
                Membership.id == mapping.id,
                Membership.tenant_id == self.principal.tenant_id,
                Membership.family_user_id == local_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if mapping is None:
            raise ApiError(403, "auth.family_mapping_required")
        count = self.control.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.identity_id == mapping.identity_id)
        )
        if identity is None or identity.is_superadmin or count != 1:
            raise ApiError(403, "auth.family_mapping_required")
        return mapping, identity

    def _revoke(self, identity_id: int) -> None:
        now = datetime.now(UTC)
        self.control.execute(
            delete(BrowserSession).where(BrowserSession.identity_id == identity_id)
        )
        self.control.execute(
            update(OAuthGrant).where(OAuthGrant.identity_id == identity_id).values(revoked_at=now)
        )
        self.control.execute(
            update(OAuthAuthorizationCode)
            .where(OAuthAuthorizationCode.identity_id == identity_id)
            .values(consumed_at=now)
        )

    def _new_identity(self, email: str, password: str) -> Identity:
        if self.control.scalar(select(Identity.id).where(Identity.email == email)) is not None:
            raise ApiError(409, "auth.email_taken")
        identity = Identity(email=email, password_hash=hash_secret(password), is_superadmin=False)
        self.control.add(identity)
        try:
            self.control.flush()
        except IntegrityError as exc:
            self.control.rollback()
            raise ApiError(409, "auth.email_taken") from exc
        return identity

    def create_unlinked(self, email: str, password: str, role: str, family_id: int) -> User:
        if role not in {"parent", "child"}:
            raise ApiError(422, "auth.invalid_role")
        if self.family.scalar(select(User.id).where(User.email == email)) is not None:
            raise ApiError(409, "auth.email_taken")
        identity = self._new_identity(email, password)
        try:
            user = self.family.scalar(
                insert(User)
                .values(email=email, password_hash="!", role=role, family_id=family_id)
                .returning(User)
            )
        except IntegrityError as exc:
            self.family.rollback()
            self.control.rollback()
            raise ApiError(409, "auth.email_taken") from exc
        assert user is not None
        self.control.add(
            Membership(
                identity_id=identity.id,
                tenant_id=self.principal.tenant_id,
                family_user_id=user.id,
                role=role,
            )
        )
        self.control.flush()
        return user

    def save_member(self, member, login, actor) -> None:
        with self.family.no_autoflush:
            user = self.family.scalar(
                select(User)
                .where(User.id == member.user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if isinstance(login, MemberExistingLogin):
                if user is not None and user.id != login.account_id:
                    raise ApiError(409, "auth.login_already_linked")
                user = self.family.scalar(
                    select(User)
                    .where(User.id == login.account_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if user is None or user.family_id != actor.user.family_id:
                    raise ApiError(404, "common.not_found")
                mapping, _ = self._mapping(user.id)
                if mapping is None:
                    raise ApiError(403, "auth.family_mapping_required")
                owner = self.family.scalar(
                    select(FamilyMember.id).where(FamilyMember.user_id == user.id)
                )
                if owner is not None and owner != member.id:
                    raise ApiError(409, "auth.login_already_linked")
                if mapping.role != member.role and not (
                    mapping.role == "admin" and member.role == "parent"
                ):
                    raise ApiError(409, "auth.login_role_mismatch")
                member.user_id = user.id
            elif isinstance(login, MemberLoginCredentials):
                duplicate = self.family.scalar(select(User.id).where(User.email == login.email))
                if duplicate is not None and (user is None or duplicate != user.id):
                    raise ApiError(409, "auth.email_taken")
                if user is None:
                    if login.password is None:
                        raise ApiError(422, "auth.login_password_required")
                    user = self.create_unlinked(
                        login.email, login.password, member.role, actor.user.family_id
                    )
                    member.user_id = user.id
                else:
                    mapping, identity = self._mapping(user.id)
                    if mapping is None:
                        # Repair a local profile left by a failed central commit.
                        if login.password is None:
                            raise ApiError(422, "auth.login_password_required")
                        identity = self._new_identity(login.email, login.password)
                        mapping = Membership(
                            identity_id=identity.id,
                            tenant_id=self.principal.tenant_id,
                            family_user_id=user.id,
                            role=user.role,
                        )
                        self.control.add(mapping)
                    duplicate_identity = self.control.scalar(
                        select(Identity.id).where(Identity.email == login.email)
                    )
                    if duplicate_identity is not None and duplicate_identity != identity.id:
                        raise ApiError(409, "auth.email_taken")
                    changed = identity.email != login.email or login.password is not None
                    identity.email = login.email
                    if login.password is not None:
                        identity.password_hash = hash_secret(login.password)
                    if changed:
                        self._revoke(identity.id)
                    user.email = login.email
            if user is None:
                return
            if user.family_id != actor.user.family_id:
                raise ApiError(404, "common.not_found")
            mapping, identity = self._mapping(user.id)
            if mapping is None:
                # New mapping may still be pending in the control session.
                self.control.flush()
                mapping, identity = self._mapping(user.id)
            if mapping is None:
                raise ApiError(403, "auth.family_mapping_required")
            if member.role == "child" and (user.role == "admin" or user.id == actor.user_id):
                raise ApiError(409, "auth.login_role_protected")
            role = "admin" if user.role == "admin" else member.role
            if mapping.role != role:
                mapping.role = role
                self._revoke(identity.id)
            user.role = role
            user.password_hash = "!"

    def commit_after_family(self) -> None:
        try:
            self.control.commit()
        except Exception as exc:
            self.control.rollback()
            logger.error(
                "Central account finalization failed for family %s", self.principal.tenant_id
            )
            raise ApiError(503, "auth.account_save_incomplete") from exc


def editor_for(db: Session) -> CentralAccountEditor:
    editor = db.info.get("central_account_editor")
    if editor is None:
        editor = CentralAccountEditor(db, db.info["central_control"], db.info["family_principal"])
        db.info["central_account_editor"] = editor
    return editor
