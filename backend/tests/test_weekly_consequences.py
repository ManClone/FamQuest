"""Contract tests for the isolated weekly bonus calculation."""

import datetime as dt

import pytest

from app.weekly_consequences import DEFAULT_CONSEQUENCES, monday_of, weekly_statement


def test_monday_to_sunday_and_penalty():
    result = weekly_statement(dt.date(2026, 10, 14), 300, 50)
    assert result.week_start == dt.date(2026, 10, 12)
    assert result.week_end == dt.date(2026, 10, 18)
    assert result.payable_bonus_cents == 250


def test_penalty_cannot_create_debt():
    result = weekly_statement(dt.date(2026, 10, 18), 300, 400)
    assert result.payable_bonus_cents == 0


def test_next_week_has_independent_period():
    assert monday_of(dt.date(2026, 10, 19)) == dt.date(2026, 10, 19)


@pytest.mark.parametrize("earned,penalty", [(-1, 0), (0, -1)])
def test_negative_inputs_rejected(earned, penalty):
    with pytest.raises(ValueError):
        weekly_statement(dt.date(2026, 10, 14), earned, penalty)


def test_default_consequence():
    assert DEFAULT_CONSEQUENCES["Nicht auf Anweisungen gehört"] == {"money_penalty_cents": 50, "xp_penalty": 5}
