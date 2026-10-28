"""Prepare an identity migration plan without changing either database."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_migration_inventory import assert_single_family_migration_ready, inspect_legacy
from app.models import Family, User


@dataclass(frozen=True)
class IdentityTransfer:
    user_id: int
    email: str
    family_id: int
    role: str


def build_identity_transfer_plan(db: Session) -> list[IdentityTransfer]:
    assert_single_family_migration_ready(inspect_legacy(db))
    family = db.scalars(select(Family)).one()
    users = db.scalars(select(User).order_by(User.id)).all()
    if any(user.family_id != family.id for user in users):
        raise ValueError("User belongs to a different family")
    return [IdentityTransfer(user.id, user.email, family.id, user.role) for user in users]
