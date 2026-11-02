"""Create families only in explicitly prepared, empty databases using dedicated roles."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import inspect, select, text

from app.auth_registry import FamilyCreation, Identity, Membership, Tenant
from app.db import Base
from app.deployment_check import migration_head
from app.errors import ApiError
from app.family_db import FamilyDatabase
from app.models import Family, FamilyMember, User
from app.schemas import Email
from app.security import hash_secret
from app.tenant_provisioning import validate_family_database_name


class CreationRequest(BaseModel):
    model_config = {"extra": "forbid"}
    request_key: UUID
    family_name: str = Field(min_length=1, max_length=100)
    parent_name: str = Field(min_length=1, max_length=50)
    parent_email: Email
    password: SecretStr = Field(min_length=16, max_length=128)
    language: Literal["de", "en"] = "de"
    timezone: str = Field(default="Europe/Berlin", max_length=64)
    confirmed: Literal[True]

    @field_validator("family_name", "parent_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("A name is required")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


def configured_slots(settings):
    names = settings.family_creation_databases
    if len(names) != len(set(names)):
        raise ValueError("Duplicate creation slot")
    for name in names:
        validate_family_database_name(name)
        credentials = settings.family_database_credentials.get(name)
        if credentials is None or credentials.username != f"{name}_app":
            raise ValueError("A dedicated prepared family role is required")
    return names


def available_slots(db, settings):
    used = set(db.scalars(select(Tenant.database_name)))
    return [name for name in configured_slots(settings) if name not in used]


class SlotNotEmpty(ValueError):
    pass


def verify_empty_slot(db):
    root = Path(__file__).resolve().parents[1]
    if db.scalars(text("SELECT version_num FROM alembic_version")).all() != [
        migration_head(root / "alembic")
    ]:
        raise ValueError("Prepared family schema is not current")
    if set(inspect(db.connection()).get_table_names()) != set(Base.metadata.tables) | {
        "alembic_version"
    }:
        raise SlotNotEmpty("Unexpected tables in prepared family database")
    for table in Base.metadata.tables.values():
        if db.execute(select(1).select_from(table).limit(1)).first() is not None:
            raise SlotNotEmpty("Prepared family database contains data")


def seed_family(router, tenant_id, database_name, request):
    with router.session(FamilyDatabase(tenant_id, database_name)) as db:
        verify_empty_slot(db)
        family = Family(
            id=1,
            name=request.family_name,
            default_language=request.language,
            timezone=request.timezone,
        )
        db.add(family)
        db.flush()
        user = User(
            email=request.parent_email, role="parent", family_id=family.id, password_hash="!"
        )
        db.add(user)
        db.flush()
        db.add(
            FamilyMember(name=request.parent_name, role="parent", color="orange", user_id=user.id)
        )
        local_id = user.id
        db.commit()
        return local_id


def submit_creation(db, settings, router, actor_id, request):
    existing = db.scalar(
        select(FamilyCreation).where(
            FamilyCreation.actor_identity_id == actor_id,
            FamilyCreation.request_key == str(request.request_key),
        )
    )
    public = (
        request.family_name,
        request.parent_name,
        request.parent_email,
        request.language,
        request.timezone,
    )
    if existing:
        if (
            existing.family_name,
            existing.parent_name,
            existing.parent_email,
            existing.language,
            existing.timezone,
        ) != public:
            raise ApiError(409, "auth.family_creation_conflict")
        # A replay never changes credentials, retries a partial seed or reuses its slot.
        return existing
    if db.scalar(select(Identity.id).where(Identity.email == request.parent_email)) is not None:
        raise ApiError(409, "auth.family_creation_conflict")
    free = available_slots(db, settings)
    if not free or router is None:
        raise ApiError(409, "auth.family_creation_capacity")
    tenant = Tenant(name=request.family_name, database_name=free[0], status="provisioning")
    parent = Identity(
        email=request.parent_email,
        password_hash=hash_secret(request.password.get_secret_value()),
        is_superadmin=False,
    )
    db.add_all([tenant, parent])
    db.flush()
    job = FamilyCreation(
        actor_identity_id=actor_id,
        request_key=str(request.request_key),
        tenant_id=tenant.id,
        parent_identity_id=parent.id,
        family_name=request.family_name,
        parent_name=request.parent_name,
        parent_email=request.parent_email,
        language=request.language,
        timezone=request.timezone,
        status="provisioning",
    )
    db.add(job)
    db.flush()
    job_id, tenant_id, parent_id, database_name = job.id, tenant.id, parent.id, tenant.database_name
    db.commit()  # Reserve before touching the other database. Partial work is never reused.
    try:
        local_id = seed_family(router, tenant_id, database_name, request)
        tenant = db.scalar(
            select(Tenant)
            .where(Tenant.id == tenant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        job = db.get(FamilyCreation, job_id, populate_existing=True)
        actor = db.get(Identity, actor_id, populate_existing=True)
        if (
            actor is None
            or not actor.is_superadmin
            or db.scalar(select(Membership.id).where(Membership.identity_id == actor_id).limit(1))
        ):
            raise PermissionError("Operator authority changed")
        if tenant.status != "provisioning" or job.status != "provisioning":
            raise ValueError("Provisioning state changed")
        db.add(
            Membership(
                identity_id=parent_id, tenant_id=tenant_id, role="parent", family_user_id=local_id
            )
        )
        tenant.status = "active"
        job.status, job.finished_at = "ready", datetime.now(UTC)
        db.commit()
    except Exception as exc:
        db.rollback()
        tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
        job = db.get(FamilyCreation, job_id, populate_existing=True)
        tenant.status = "provisioning_failed"
        job.status = "failed"
        job.error_code = "slot_not_empty" if isinstance(exc, SlotNotEmpty) else "setup_failed"
        job.finished_at = datetime.now(UTC)
        db.commit()
    return job


def creation_out(job):
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "family_name": job.family_name,
        "parent_name": job.parent_name,
        "parent_email": job.parent_email,
        "status": job.status,
        "error_code": job.error_code,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
