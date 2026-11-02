"""Opt-in background jobs with explicit registered family database connections."""

import asyncio
import time
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.auth_registry import Tenant
from app.family_db import FamilyDatabase
from app.logs import logger


def active(registry, family):
    with registry.session() as control:
        current = control.get(Tenant, family.family_id)
        return (
            current is not None
            and current.status == "active"
            and current.database_name == family.database_name
        )


def run_once(registry, router, *, allowances, calendar, allowance_job=None, calendar_job=None):
    from app.calendar_sync import sync_all
    from app.money import run_weekly_allowance_check

    allowance_job = allowance_job or run_weekly_allowance_check
    calendar_job = calendar_job or sync_all
    with registry.session() as control:
        families = [
            FamilyDatabase(tenant.id, tenant.database_name)
            for tenant in control.scalars(
                select(Tenant).where(Tenant.status == "active").order_by(Tenant.id)
            )
        ]
    for family in families:
        try:
            # Revalidate after enumeration; a disabled/remapped family never falls
            # back to the legacy global engine or another family's credentials.
            if not active(registry, family):
                continue
            with router.session(family) as db:
                engine = db.get_bind()
            if allowances and active(registry, family):
                allowance_job(database_engine=engine)
            if calendar and active(registry, family):
                calendar_job(database_engine=engine, session_factory=sessionmaker(bind=engine))
        except Exception:
            # No names, credentials or family data in logs. One failure must not
            # prevent another family's independent check.
            logger.exception("Background check failed for registered family %s", family.family_id)


async def run_periodically(registry, router, settings):
    last_allowance = None
    last_calendar = None
    while True:
        now = time.monotonic()
        allowances = last_allowance is None or now - last_allowance >= 3600
        calendar = (
            settings.central_calendar_jobs
            and settings.calendar_sync_minutes > 0
            and (
                last_calendar is None or now - last_calendar >= settings.calendar_sync_minutes * 60
            )
        )
        try:
            if allowances or calendar:
                work = asyncio.create_task(
                    asyncio.to_thread(
                        run_once, registry, router, allowances=allowances, calendar=calendar
                    )
                )
                try:
                    await asyncio.shield(work)
                except asyncio.CancelledError:
                    # Do not dispose a family's engine while its worker is still
                    # committing. Shutdown waits for this in-flight check only.
                    with suppress(Exception):
                        await work
                    raise
                if allowances:
                    last_allowance = now
                if calendar:
                    last_calendar = now
        except Exception:
            logger.exception("Central background family enumeration failed")
        await asyncio.sleep(60)
