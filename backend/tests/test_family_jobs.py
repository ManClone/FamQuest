"""No scheduler job can accidentally use the global single-family connection."""

from sqlalchemy.orm import Session

from app.auth_registry import Tenant
from app.family_jobs import run_once
from app.models import Family
from tests import test_multitenant_app

environment = test_multitenant_app.environment


def test_jobs_have_separate_explicit_engines_and_calendar_sessions(environment):
    _, registry, router, _ = environment
    allowances, calendars = [], []

    def allowance(*, database_engine):
        with Session(database_engine) as db:
            allowances.append(db.get(Family, 1).name)

    def calendar(*, database_engine, session_factory):
        with session_factory() as db:
            assert db.get_bind() is database_engine
            calendars.append(db.get(Family, 1).name)

    run_once(
        registry,
        router,
        allowances=True,
        calendar=True,
        allowance_job=allowance,
        calendar_job=calendar,
    )
    assert allowances == calendars == ["Sertl", "Henning"]


def test_disabled_family_skipped_and_one_failure_does_not_block_other_family(environment):
    _, registry, router, _ = environment
    calls = []

    def allowance(*, database_engine):
        with Session(database_engine) as db:
            name = db.get(Family, 1).name
        calls.append(name)
        if name == "Sertl":
            raise RuntimeError("Simulated independent family failure")

    run_once(registry, router, allowances=True, calendar=False, allowance_job=allowance)
    assert calls == ["Sertl", "Henning"]
    calls.clear()
    with registry.session() as db:
        db.get(Tenant, 1).status = "disabled"
        db.commit()
    run_once(registry, router, allowances=True, calendar=False, allowance_job=allowance)
    assert calls == ["Henning"]


def test_calendar_remains_off_when_not_explicitly_requested(environment):
    _, registry, router, _ = environment
    calls = []

    def forbidden(**kwargs):
        calls.append(True)

    run_once(registry, router, allowances=False, calendar=False, calendar_job=forbidden)
    assert calls == []


def test_family_disabled_between_jobs_is_not_used_for_calendar(environment):
    _, registry, router, _ = environment
    calendars = []

    def allowance(*, database_engine):
        with registry.session() as control:
            control.get(Tenant, 1).status = "disabled"
            control.commit()

    def calendar(*, database_engine, session_factory):
        with session_factory() as db:
            calendars.append(db.get(Family, 1).name)

    run_once(
        registry,
        router,
        allowances=True,
        calendar=True,
        allowance_job=allowance,
        calendar_job=calendar,
    )
    assert calendars == ["Henning"]
