"""Deterministic weekly assignment suggestions for adult household chores.

No database writes: callers may preview and override the plan before publishing.
"""
from dataclasses import dataclass
from typing import Literal

Mode = Literal["fixed", "rotate", "flexible"]


@dataclass(frozen=True)
class HouseholdChore:
    id: int
    minutes: int
    mode: Mode = "flexible"
    fixed_member_id: int | None = None

    def __post_init__(self) -> None:
        if self.minutes <= 0:
            raise ValueError("minutes must be positive")
        if self.mode == "fixed" and self.fixed_member_id is None:
            raise ValueError("fixed chores require a member")


def suggest_week(
    chores: list[HouseholdChore],
    adult_ids: list[int],
    previous_minutes: dict[int, int] | None = None,
    previous_assignees: dict[int, int] | None = None,
) -> dict[int, int]:
    """Return chore_id -> member_id, minimizing projected time per adult.

    Fixed chores are allocated first and count toward the total load.
    Rotating chores prefer someone other than last week's assignee.
    Flexible chores go to the currently least-loaded adult.
    """
    members = sorted(set(adult_ids))
    if not members:
        raise ValueError("at least one adult is required")
    if len({chore.id for chore in chores}) != len(chores):
        raise ValueError("duplicate chore ids")
    previous_minutes = previous_minutes or {}
    previous_assignees = previous_assignees or {}
    load = {member: max(0, previous_minutes.get(member, 0)) for member in members}
    assignments: dict[int, int] = {}

    for chore in sorted(chores, key=lambda c: c.id):
        if chore.mode != "fixed":
            continue
        if chore.fixed_member_id not in load:
            raise ValueError("fixed member must be an adult in this plan")
        assignments[chore.id] = chore.fixed_member_id
        load[chore.fixed_member_id] += chore.minutes

    remaining = sorted(
        (c for c in chores if c.mode != "fixed"),
        key=lambda c: (-c.minutes, c.id),
    )
    for chore in remaining:
        candidates = members
        if chore.mode == "rotate" and len(members) > 1:
            alternatives = [m for m in members if m != previous_assignees.get(chore.id)]
            if alternatives:
                candidates = alternatives
        chosen = min(candidates, key=lambda member: (load[member], member))
        assignments[chore.id] = chosen
        load[chosen] += chore.minutes
    return assignments
