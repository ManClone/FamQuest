"""Praise is recorded independently of stars, money and experience."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import FamilyMember, Praise
from app.points import lock_member


def grant_praise(db: Session, member_id: int, user_id: int, reason: str, source_key: str) -> Praise:
    lock_member(db, member_id)
    member = db.get(FamilyMember, member_id)
    if member is None or member.role != "child":
        raise ApiError(422, "praise.child_required")
    existing = db.scalar(select(Praise).where(Praise.source_key == source_key))
    if existing:
        if existing.member_id != member_id or existing.reason != reason:
            raise ApiError(409, "praise.request_conflict")
        return existing
    entry = Praise(
        member_id=member_id, created_by_user_id=user_id, reason=reason, source_key=source_key
    )
    db.add(entry)
    db.flush()
    from app.levels import advance

    advance(db, member_id)
    return entry
