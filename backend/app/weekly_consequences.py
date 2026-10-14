"""Pure weekly euro-bonus accounting, independent of XP and base allowance."""

import datetime as dt
from dataclasses import dataclass


# Initial suggestion; parents will be able to customize both deductions.
DEFAULT_CONSEQUENCES = {
    "Nicht auf Anweisungen gehört": {"money_penalty_cents": 50, "xp_penalty": 5}
}


@dataclass(frozen=True)
class WeeklyBonusStatement:
    week_start: dt.date
    week_end: dt.date
    earned_bonus_cents: int
    money_penalty_cents: int
    payable_bonus_cents: int


def monday_of(day: dt.date) -> dt.date:
    """Start of the family-local ISO week."""
    return day - dt.timedelta(days=day.weekday())


def weekly_statement(
    day: dt.date, earned_bonus_cents: int, money_penalty_cents: int
) -> WeeklyBonusStatement:
    """Compute the payable weekly *money* bonus in integer cents.

    Excess penalties expire at week end. This pure function does not
    book money, change spendable XP, level XP, or base allowance.
    """
    if earned_bonus_cents < 0 or money_penalty_cents < 0:
        raise ValueError("Weekly money amounts must be nonnegative")
    start = monday_of(day)
    return WeeklyBonusStatement(
        week_start=start,
        week_end=start + dt.timedelta(days=6),
        earned_bonus_cents=earned_bonus_cents,
        money_penalty_cents=money_penalty_cents,
        payable_bonus_cents=max(0, earned_bonus_cents - money_penalty_cents),
    )
