"""Pure weekly bonus accounting; never changes lifetime XP or allowance."""

import datetime as dt
from dataclasses import dataclass


DEFAULT_CONSEQUENCES = {"Nicht auf Anweisungen gehört": 5}


@dataclass(frozen=True)
class WeeklyBonusStatement:
    week_start: dt.date
    week_end: dt.date
    earned_bonus_points: int
    penalty_points: int
    payable_bonus_points: int


def monday_of(day: dt.date) -> dt.date:
    """Start of the family-local ISO week."""
    return day - dt.timedelta(days=day.weekday())


def weekly_statement(
    day: dt.date, earned_bonus_points: int, penalty_points: int
) -> WeeklyBonusStatement:
    """Calculate a nonnegative weekly bonus without touching lifetime XP.

    Callers must provide *weekly bonus* points, not the lifetime XP balance.
    This calculation neither modifies nor schedules unconditional allowance.
    """
    if earned_bonus_points < 0 or penalty_points < 0:
        raise ValueError("Weekly earned and penalty points must be nonnegative")
    start = monday_of(day)
    return WeeklyBonusStatement(
        week_start=start,
        week_end=start + dt.timedelta(days=6),
        earned_bonus_points=earned_bonus_points,
        penalty_points=penalty_points,
        payable_bonus_points=max(0, earned_bonus_points - penalty_points),
    )
