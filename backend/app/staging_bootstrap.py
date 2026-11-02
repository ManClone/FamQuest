"""Explicit bootstrap of a NEW, isolated PostgreSQL staging cluster. Never restore or drop."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth_db import AuthDatabase
from app.auth_registry import Identity, Membership, Tenant
from app.config import Settings
from app.deployment_check import migration_head, verify
from app.family_db import FamilyDatabaseRouter
from app.models import Family, FamilyMember, User
from app.security import hash_secret
from app.tenant_provisioner import provision_empty_family

DATABASES = ("famquest_stage_a", "famquest_stage_b")
SPARE_DATABASES = ("famquest_stage_c", "famquest_stage_d")
AUTH_DB = "famquest_auth"
OWNER = "famquest_stage_owner"
HOST = "central-stage-db"
MARKER = "famquest_central_stage_v1"
LOCK = 603011902


def validated_inputs(settings, environ):
    if environ.get("FAMQUEST_STAGE_BOOTSTRAP") != "new-isolated-cluster-v1":
        raise ValueError("Explicit isolated staging mode required")
    if settings.postgres_host != HOST or settings.postgres_user != OWNER:
        raise ValueError("Only the dedicated staging database host and owner are allowed")
    origin = urlsplit(settings.public_url)
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.path not in ("", "/")
        or origin.query
        or origin.fragment
    ):
        raise ValueError("An HTTPS staging origin is required")
    if settings.demo_mode or settings.central_background_jobs or settings.central_calendar_jobs:
        raise ValueError("Staging initialization requires demo and background jobs disabled")
    auth = settings.auth_database_credentials
    if auth is None or auth.username != "famquest_auth_app":
        raise ValueError("Dedicated registry credentials required")
    slots = settings.family_creation_databases
    if len(slots) != len(set(slots)) or not set(slots).issubset(SPARE_DATABASES):
        raise ValueError("Only the two fixed additional staging slots are allowed")
    databases = (*DATABASES, *slots)
    if set(settings.family_database_credentials) != set(databases):
        raise ValueError("Only the configured staging family databases are allowed")
    secrets = [settings.postgres_password, auth.password]
    for name in databases:
        credentials = settings.family_database_credentials[name]
        if credentials.username != f"{name}_app":
            raise ValueError("Unexpected staging family role")
        secrets.append(credentials.password)
    database_secret_count = len(secrets)
    accounts = {}
    for family in ("A", "B"):
        for role in ("PARENT", "CHILD"):
            value = environ.get(f"STAGE_{family}_{role}_PASSWORD", "")
            if not 16 <= len(value) <= 128:
                raise ValueError("Four independently generated staging login passwords required")
            accounts[(family, role)] = value
            secrets.append(value)
    if any(len(value) < 32 for value in secrets[:database_secret_count]) or len(
        set(secrets)
    ) != len(secrets):
        raise ValueError("Independent strong staging credentials required")
    return accounts


def inspect_cluster(conn, origin, databases=DATABASES):
    """Return fresh/ready, refusing foreign or partial clusters before writing anything."""
    actual_databases = set(
        conn.scalars(text("SELECT datname FROM pg_database WHERE NOT datistemplate"))
    )
    marker = conn.scalar(text("SELECT to_regclass('public.famquest_central_stage_v1')"))
    roles = set(conn.scalars(text("SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%'")))
    expected_roles = {OWNER, "famquest_auth_app", *(f"{name}_app" for name in databases)}
    if marker is None:
        if actual_databases != {"postgres"} or roles != {OWNER}:
            raise RuntimeError("Database cluster is not empty; refusing existing or partial data")
        tables = conn.scalar(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        )
        if tables:
            raise RuntimeError("Existing public tables; refusing to initialize")
        return "fresh"
    if actual_databases != {"postgres", AUTH_DB, *databases} or roles != expected_roles:
        raise RuntimeError("Staging database or role inventory changed; manual review required")
    recorded = conn.scalars(text("SELECT origin FROM public.famquest_central_stage_v1")).all()
    if recorded != [origin.rstrip("/")]:
        raise RuntimeError("Staging origin differs; no automatic overwrite")
    return "ready"


def _registry_database(conn, password):
    conn.exec_driver_sql('CREATE ROLE "famquest_auth_app" LOGIN NOINHERIT')
    with conn.connection.driver_connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("ALTER ROLE famquest_auth_app PASSWORD {}").format(sql.Literal(password))
        )
    conn.exec_driver_sql('CREATE DATABASE "famquest_auth" OWNER "famquest_auth_app"')
    conn.exec_driver_sql('REVOKE CONNECT ON DATABASE "famquest_auth" FROM PUBLIC')
    conn.exec_driver_sql('GRANT CONNECT ON DATABASE "famquest_auth" TO "famquest_auth_app"')


def _migrate(settings, name, credentials, auth=False):
    engine = create_engine(
        settings.database_url(name).set(
            username=credentials.username, password=credentials.password
        )
    )
    root = Path(__file__).resolve().parents[1]
    config = Config(root / ("auth_alembic.ini" if auth else "alembic.ini"))
    config.attributes.update(database_url=engine.url, configure_logger=False)
    try:
        command.upgrade(config, "head")
    except Exception:
        engine.dispose()
        raise
    return engine


def check_ready(settings):
    registry = AuthDatabase(settings)
    router = FamilyDatabaseRouter(settings)
    root = Path(__file__).resolve().parents[1]
    try:
        return verify(
            registry,
            router,
            auth_head=migration_head(root / "auth_alembic"),
            family_head=migration_head(root / "alembic"),
        )
    finally:
        router.close()
        registry.close()


def bootstrap(settings=None, environ=None):
    settings = settings or Settings()
    accounts = validated_inputs(settings, os.environ if environ is None else environ)
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    engines = []
    try:
        with admin.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK})
            try:
                state = inspect_cluster(
                    conn, settings.public_url, (*DATABASES, *settings.family_creation_databases)
                )
                if state == "ready":
                    check_ready(settings)
                    return "already-ready"
                _registry_database(conn, settings.auth_database_credentials.password)
                for name in (*DATABASES, *settings.family_creation_databases):
                    provision_empty_family(
                        admin, name, settings.family_database_credentials[name].password
                    )
                auth_engine = _migrate(
                    settings, AUTH_DB, settings.auth_database_credentials, auth=True
                )
                engines.append(auth_engine)
                with Session(auth_engine) as auth:
                    for label, name in zip(("A", "B"), DATABASES, strict=True):
                        credentials = settings.family_database_credentials[name]
                        engine = _migrate(settings, name, credentials)
                        engines.append(engine)
                        tenant = Tenant(
                            name=f"Testfamilie {label}", database_name=name, status="active"
                        )
                        auth.add(tenant)
                        auth.flush()
                        with Session(engine) as family:
                            family.add(
                                Family(
                                    id=1,
                                    name=tenant.name,
                                    default_language="de",
                                    timezone="Europe/Berlin",
                                )
                            )
                            family.flush()
                            for role, title, color in (
                                ("PARENT", "Eltern", "orange"),
                                ("CHILD", "Kind", "red"),
                            ):
                                prefix = "eltern" if role == "PARENT" else "kind"
                                email = f"{prefix}.{label.lower()}@famquest.test"
                                local_role = "parent" if role == "PARENT" else "child"
                                user = User(
                                    family_id=1, email=email, role=local_role, password_hash="!"
                                )
                                family.add(user)
                                family.flush()
                                family.add(
                                    FamilyMember(
                                        name=f"{title} {label}",
                                        role=local_role,
                                        color=color,
                                        user_id=user.id,
                                    )
                                )
                                identity = Identity(
                                    email=email,
                                    password_hash=hash_secret(accounts[(label, role)]),
                                    is_superadmin=False,
                                )
                                auth.add(identity)
                                auth.flush()
                                auth.add(
                                    Membership(
                                        identity_id=identity.id,
                                        tenant_id=tenant.id,
                                        role=local_role,
                                        family_user_id=user.id,
                                    )
                                )
                            family.commit()
                    for name in settings.family_creation_databases:
                        engines.append(
                            _migrate(settings, name, settings.family_database_credentials[name])
                        )
                    auth.commit()
                check_ready(settings)
                conn.exec_driver_sql(
                    "CREATE TABLE public.famquest_central_stage_v1 (origin text NOT NULL)"
                )
                conn.execute(
                    text("INSERT INTO public.famquest_central_stage_v1 VALUES (:origin)"),
                    {"origin": settings.public_url.rstrip("/")},
                )
                return "initialized"
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
    finally:
        for engine in engines:
            engine.dispose()
        admin.dispose()


def main():
    try:
        result = bootstrap()
    except Exception:
        # Never print connection strings, password-bearing SQL or seed inputs.
        print(
            "Staging initialization refused or failed. "
            "No existing data is overwritten; review the isolated test setup.",
            flush=True,
        )
        raise SystemExit(1) from None
    print(f"Staging {result}: separate registry and two families verified; no secrets printed.")


if __name__ == "__main__":
    main()
