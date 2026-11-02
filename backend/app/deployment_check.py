"""Read-only central deployment preflight. Never migrate or repair data here."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text

from app.auth_db import AuthDatabase
from app.auth_registry import Identity, Membership, Tenant
from app.config import get_settings
from app.family_db import FamilyDatabase, FamilyDatabaseRouter
from app.family_principal import resolve_family_principal
from app.models import User
from app.multitenant_app import local_actor


def migration_head(directory):
    config = Config()
    config.set_main_option("script_location", str(directory))
    return ScriptDirectory.from_config(config).get_current_head()


def verify(registry, router, *, auth_head, family_head):
    checked = []
    with registry.session() as control:
        if control.scalars(text("SELECT version_num FROM alembic_version")).all() != [auth_head]:
            raise RuntimeError("Central registry migrations are not current")
        families = list(
            control.scalars(select(Tenant).where(Tenant.status == "active").order_by(Tenant.id))
        )
        if not families:
            disabled = control.scalar(select(Tenant.id).where(Tenant.status == "disabled").limit(1))
            operator = control.scalar(
                select(Identity.id)
                .where(
                    Identity.is_superadmin.is_(True),
                    ~select(Membership.id).where(Membership.identity_id == Identity.id).exists(),
                )
                .limit(1)
            )
            if disabled is None or operator is None:
                raise RuntimeError("No active family has been explicitly provisioned")
            # Keep recovery through the separate operator console available.
            # No disabled family connection is opened or automatically migrated.
        for tenant in families:
            family = FamilyDatabase(tenant.id, tenant.database_name)
            with router.session(family) as db:
                if db.scalars(text("SELECT version_num FROM alembic_version")).all() != [
                    family_head
                ]:
                    raise RuntimeError("A family database requires an explicit migration")
                links = control.scalars(
                    select(Membership).where(Membership.tenant_id == tenant.id)
                ).all()
                if not links or not any(link.role in {"admin", "parent"} for link in links):
                    raise RuntimeError("An active family has no mapped parent account")
                for link in links:
                    principal = resolve_family_principal(control, link.identity_id)
                    local_actor(db, principal)
                if any(user.password_hash != "!" for user in db.scalars(select(User))):
                    raise RuntimeError("Family-local login hashes require explicit removal")
                checked.append(tenant.id)
    return checked


def main():
    settings = get_settings()
    if settings.demo_mode:
        raise RuntimeError("Central deployment cannot use demo mode")
    registry = AuthDatabase(settings)
    router = FamilyDatabaseRouter(settings)
    root = Path(__file__).resolve().parents[1]
    try:
        families = verify(
            registry,
            router,
            auth_head=migration_head(root / "auth_alembic"),
            family_head=migration_head(root / "alembic"),
        )
        print(f"Read-only preflight passed for {len(families)} active families; no data modified")
    finally:
        router.close()
        registry.close()


if __name__ == "__main__":
    main()
