"""Parent-only preview of weekly bonus arithmetic (no database writes)."""

import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.members import get_member
from app.auth import DbSession, ParentSession
from app.errors import ApiError
from app.weekly_consequences import weekly_statement

router = APIRouter(tags=["weekly-consequences"])


class WeeklyPreviewIn(BaseModel):
    member_id: int
    date: dt.date
    earned_bonus_points: int = Field(ge=0, le=100000)
    penalty_points: int = Field(ge=0, le=100000)


class WeeklyPreviewOut(BaseModel):
    member_id: int
    week_start: dt.date
    week_end: dt.date
    earned_bonus_points: int
    penalty_points: int
    payable_bonus_points: int


@router.post("/weekly-consequences/preview", response_model=WeeklyPreviewOut)
def preview_weekly_consequences(
    body: WeeklyPreviewIn, _: ParentSession, db: DbSession
) -> WeeklyPreviewOut:
    """Simulate a week's penalty deductions without changing XP or allowance."""
    member = get_member(db, body.member_id)
    if member.role != "child":
        raise ApiError(422, "money.child_required")
    result = weekly_statement(body.date, body.earned_bonus_points, body.penalty_points)
    return WeeklyPreviewOut(member_id=member.id, **result.__dict__)
