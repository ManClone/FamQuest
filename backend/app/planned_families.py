"""Planned additional families; no database or user is created by importing this."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedFamily:
    name: str
    database_name: str


ADDITIONAL_FAMILIES = (
    PlannedFamily(name="Sertl", database_name="famquest_sertl"),
    PlannedFamily(name="Henning", database_name="famquest_henning"),
)
