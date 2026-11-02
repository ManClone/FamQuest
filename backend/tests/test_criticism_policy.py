import pytest

from app.criticism_policy import amounts


@pytest.mark.parametrize(
    "level,stars", [("conversation", 0), ("light", 1), ("heavy", 2), ("severe", 3)]
)
def test_stars_only_never_touch_euros_or_require_a_bonus(level, stars):
    assert amounts(level, apply_money=False, available_bonus=0, closed=True) == (stars, 0)


@pytest.mark.parametrize("level,money", [("heavy", 50), ("severe", 100)])
def test_explicit_euro_deduction_requires_positive_remainder_and_open_week(level, money):
    assert amounts(level, apply_money=True, available_bonus=money + 1, closed=False)[1] == money
    for available in (0, money - 1, money):
        with pytest.raises(ValueError):
            amounts(level, apply_money=True, available_bonus=available, closed=False)
    with pytest.raises(ValueError):
        amounts(level, apply_money=True, available_bonus=1000, closed=True)


@pytest.mark.parametrize("level", ["conversation", "light", "custom"])
def test_arbitrary_or_ineligible_money_levels_are_rejected(level):
    with pytest.raises(ValueError):
        amounts(level, apply_money=True, available_bonus=1000, closed=False)
