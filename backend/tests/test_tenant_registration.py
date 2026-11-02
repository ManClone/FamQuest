"""Tenant registration never activates families or creates family databases."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_registry import AuthBase, Tenant
from app.tenant_registration import stage_planned_families


def test_stage_two_disabled_families_idempotently():
    engine = create_engine("sqlite://")
    AuthBase.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            assert stage_planned_families(session) == 2
            session.commit()
            assert stage_planned_families(session) == 2
            tenants = session.scalars(select(Tenant).order_by(Tenant.name)).all()
            assert [(t.name, t.database_name, t.status) for t in tenants] == [
                ("Henning", "famquest_henning", "disabled"),
                ("Sertl", "famquest_sertl", "disabled"),
            ]
    finally:
        engine.dispose()
