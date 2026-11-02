"""Fixed parent-selected criticism levels; stars, level XP and euros stay separate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticismLevel:
    stars: int
    bonus_cents: int


LEVELS = {
    "conversation": CriticismLevel(0, 0),
    "light": CriticismLevel(1, 0),
    "heavy": CriticismLevel(2, 50),
    "severe": CriticismLevel(3, 100),
}


def amounts(severity: str, *, apply_money: bool, available_bonus: int, closed: bool):
    if severity not in LEVELS or type(apply_money) is not bool or available_bonus < 0:
        raise ValueError("Invalid criticism selection")
    level = LEVELS[severity]
    money = level.bonus_cents if apply_money else 0
    if apply_money and level.bonus_cents == 0:
        raise ValueError("This level has no monetary deduction")
    if money and (closed or available_bonus <= money):
        raise ValueError("A positive unpaid earned bonus must remain")
    return level.stars, money
