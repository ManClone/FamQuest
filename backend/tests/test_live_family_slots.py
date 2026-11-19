import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import live_family_slots as slots
from app.config import Settings
from app.family_creation import verify_empty_slot
from app.tenant_provisioner import provision_empty_family
from app.tenant_provisioning import quoted_identifier


@pytest.fixture
def maintenance(tmp_path, monkeypatch):
    settings = Settings()
    url = settings.database_url("postgres")
    name = f"famquest_slot_ci_{uuid4().hex[:10]}"
    existing = f"{name}_existing"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    provision_empty_family(admin, existing, "b" * 48)
    with admin.connect() as conn:
        marker_url = settings.database_url(existing)
    marker = create_engine(marker_url)
    with marker.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE preserved_marker (value text)")
        conn.exec_driver_sql("INSERT INTO preserved_marker VALUES ('existing family unchanged')")
    marker.dispose()
    admin.dispose()
    runtime = tmp_path / "runtime.json"
    values = {
        "POSTGRES_HOST": settings.postgres_host,
        "POSTGRES_PORT": str(settings.postgres_port),
        "PUBLIC_URL": "https://famquest.websiteclone.de",
        "AUTH_DATABASE_CREDENTIALS": json.dumps(
            {
                "username": "famquest_auth_app",
                "password": "a" * 48,
            }
        ),
        "FAMILY_DATABASE_CREDENTIALS": json.dumps(
            {
                existing: {"username": f"{existing}_app", "password": "b" * 48},
            }
        ),
        "FAMILY_CREATION_DATABASES": "[]",
        "TOKEN_ENCRYPTION_KEY": "unchanged-private-value",
    }
    runtime.write_text(json.dumps(values))
    checked = []
    monkeypatch.setattr(slots, "check_registry", lambda settings, name: checked.append(name))

    def prepare():
        return slots.prepare(runtime, name, url, expected_host=settings.postgres_host)

    yield runtime, name, values, checked, prepare
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            for database in (name, existing):
                conn.exec_driver_sql(
                    f"DROP DATABASE IF EXISTS {quoted_identifier(database)} WITH (FORCE)"
                )
                conn.exec_driver_sql(f"DROP ROLE IF EXISTS {quoted_identifier(database + '_app')}")
    finally:
        admin.dispose()


def test_new_slot_is_empty_restricted_and_preserves_existing_configuration(maintenance):
    runtime, name, original, checked, prepare = maintenance
    prepare()
    assert checked == [name]
    updated = json.loads(runtime.read_text())
    for key in original.keys() - {"FAMILY_DATABASE_CREDENTIALS", "FAMILY_CREATION_DATABASES"}:
        assert updated[key] == original[key]
    mapping = json.loads(updated["FAMILY_DATABASE_CREDENTIALS"])
    existing = f"{name}_existing"
    assert mapping[existing] == json.loads(original["FAMILY_DATABASE_CREDENTIALS"])[existing]
    assert json.loads(updated["FAMILY_CREATION_DATABASES"]) == [name]
    assert runtime.stat().st_mode & 0o777 == 0o600
    backup = runtime.with_name(f"runtime.before-{name}.json")
    assert json.loads(backup.read_text()) == original
    assert backup.stat().st_mode & 0o777 == 0o600
    credential = mapping[name]
    engine = create_engine(
        Settings()
        .database_url(name)
        .set(
            **{
                "username": credential["username"],
                "password": credential["password"],
            }
        )
    )
    try:
        with Session(engine) as db:
            verify_empty_slot(db)
            role = db.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            assert tuple(role) == (False, False, False)
    finally:
        engine.dispose()
    forbidden = create_engine(
        Settings()
        .database_url(existing)
        .set(
            username=credential["username"],
            password=credential["password"],
        )
    )
    try:
        with pytest.raises(OperationalError), forbidden.connect():
            pass
    finally:
        forbidden.dispose()
    marker = create_engine(Settings().database_url(existing))
    try:
        with marker.connect() as conn:
            assert (
                conn.scalar(text("SELECT value FROM preserved_marker"))
                == "existing family unchanged"
            )
    finally:
        marker.dispose()
    with pytest.raises(ValueError, match="already configured"):
        prepare()


def test_failed_new_schema_keeps_original_runtime_and_refuses_retry(maintenance, monkeypatch):
    runtime, name, original, _, prepare = maintenance

    def fail(*args):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(slots, "_migrate", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        prepare()
    assert json.loads(runtime.read_text()) == original
    assert runtime.with_name(f"runtime.before-{name}.json").exists()
    with pytest.raises(ValueError, match="Previous maintenance"):
        prepare()
    admin = create_engine(Settings().database_url("postgres"))
    try:
        with admin.connect() as conn:
            assert conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": name}
            )
    finally:
        admin.dispose()


def test_wrong_origin_and_existing_role_refused_before_config_backup(maintenance):
    runtime, name, original, _, prepare = maintenance
    runtime.write_text(json.dumps({**original, "PUBLIC_URL": "https://famtest.websiteclone.de"}))
    with pytest.raises(ValueError, match="Unexpected production"):
        prepare()
    runtime.write_text(json.dumps(original))
    admin = create_engine(Settings().database_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"CREATE ROLE {quoted_identifier(name + '_app')}")
        with pytest.raises(ValueError, match="Database or role exists"):
            prepare()
        assert not runtime.with_name(f"runtime.before-{name}.json").exists()
        assert json.loads(runtime.read_text()) == original
    finally:
        admin.dispose()
