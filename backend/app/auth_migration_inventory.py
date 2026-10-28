"""Read-only inventory for splitting legacy FamQuest into auth and family DBs.

This deliberately does not create, copy, delete, or mutate any database.
Run against a restored backup first, never as an implicit startup migration.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuthSession, Family, FamilyMember, User


@dataclass(frozen=True)
class LegacyInventory:
    family_count: int
    user_count: int
    session_count: int
    member_count: int
    unassigned_users: int
    linked_members: int


def inspect_legacy(db: Session) -> LegacyInventory:
    return LegacyInventory(
        family_count=db.scalar(select(func.count()).select_from(Family)) or 0,
        user_count=db.scalar(select(func.count()).select_from(User)) or 0,
        session_count=db.scalar(select(func.count()).select_from(AuthSession)) or 0,
        member_count=db.scalar(select(func.count()).select_from(FamilyMember)) or 0,
        unassigned_users=db.scalar(
            select(func.count()).select_from(User).where(User.family_id.is_(None))
        )
        or 0,
        linked_members=db.scalar(
            select(func.count())
            .select_from(FamilyMember)
            .where(FamilyMember.user_id.is_not(None))
        )
        or 0,
    )


def assert_single_family_migration_ready(inventory: LegacyInventory) -> None:
    """Fail closed before any future data-copy operation."""
    if inventory.family_count != 1:
        raise ValueError("Expected exactly one existing family")
    if inventory.unassigned_users:
        raise ValueError("Legacy users without family ownership require review")
