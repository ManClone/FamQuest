"""Persistent level unlocks; spendable stars and praise remain separate."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import FamilyMember, Praise


def threshold(level: int) -> int:
    if level <= 1:
        return 0
    if level == 2:
        return 50
    return 50 + 60 * (level - 2) + 5 * (level - 3) * (level - 2) // 2


def required_praise(level: int) -> int:
    # Once a milestone is unlocked, revoking praise must not add a new gate
    # to the ordinary levels after it. Only the next milestone checks live praise.
    return {4: 1, 7: 2, 10: 3}.get(level, 0)


def valid_praise(db: Session, member_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Praise)
            .where(Praise.member_id == member_id, Praise.revoked_at.is_(None))
        )
        or 0
    )


def unlocked_level(earned: int, praise: int, previous: int = 1) -> int:
    level = previous
    while earned >= threshold(level + 1) and praise >= required_praise(level + 1):
        level += 1
    return level


def advance(db: Session, member_id: int) -> None:
    """Caller holds the member lock; persist before a correction can remove its inputs."""
    from app.points import level_xp

    member = db.get(FamilyMember, member_id)
    level = unlocked_level(
        level_xp(db, member_id), valid_praise(db, member_id), member.highest_level
    )
    db.execute(
        update(FamilyMember)
        .where(FamilyMember.id == member_id)
        .values(highest_level=func.greatest(FamilyMember.highest_level, level))
    )
    db.expire(member, ["highest_level"])


def progress(db: Session, member_id: int) -> dict[str, int]:
    from app.points import level_xp

    earned = level_xp(db, member_id)
    praise = valid_praise(db, member_id)
    member = db.get(FamilyMember, member_id)
    level = unlocked_level(earned, praise, member.highest_level)
    start, target = threshold(level), threshold(level + 1)
    needed = required_praise(level + 1)
    return {
        "earned_xp": earned,
        "level": level,
        "level_progress": min(target - start, max(0, earned - start)),
        "level_size": target - start,
        "remaining_xp": max(0, target - earned),
        "next_level_xp": target,
        "required_praise": needed,
        "remaining_praise": max(0, needed - praise),
        "praise_progress": min(praise, needed),
    }
