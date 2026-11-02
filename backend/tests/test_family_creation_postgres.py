from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError

from app.auth_registry import FamilyCreation, Tenant
from app.config import FamilyDatabaseCredentials, Settings
from app.family_creation import SlotNotEmpty, verify_empty_slot
from app.family_db import FamilyDatabase
from app.models import Family
from app.operator_setup import create_operator
from app.staging_bootstrap import _migrate
from app.tenant_provisioner import provision_empty_family
from app.tenant_provisioning import quoted_identifier
from tests.test_central_auth import ORIGIN
from tests.test_multitenant_postgres import isolated_databases as isolated_databases

PASSWORD = "new-family-parent-test-password"


def test_existing_family_database_is_never_reused(isolated_databases):
    app, names, _ = isolated_databases
    with app.state.family_router.session(FamilyDatabase(1, names[1])) as db:
        with pytest.raises(SlotNotEmpty):
            verify_empty_slot(db)
        assert db.get(Family, 1).name == "Sertl"


def test_parallel_creation_uses_one_new_database_and_parent_role(isolated_databases):
    app, names, existing_password = isolated_databases
    settings = Settings()
    name = f"famquest_creation_{uuid4().hex[:12]}"
    password = "creation-database-only-" + uuid4().hex
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    made = False
    engine = None
    try:
        provision_empty_family(admin, name, password)
        made = True
        credentials = FamilyDatabaseCredentials(username=f"{name}_app", password=password)
        engine = _migrate(settings, name, credentials)
        router = app.state.family_router
        router._settings.family_database_credentials[name] = credentials
        router._settings.family_creation_databases.append(name)
        registry = app.state.auth_registry
        with registry.session() as db:
            create_operator(db, "operator@example.invalid", PASSWORD)
            db.commit()
        request = {
            "request_key": str(uuid4()),
            "family_name": "New isolated family",
            "parent_name": "New parent",
            "parent_email": "created@example.invalid",
            "password": PASSWORD,
            "language": "de",
            "timezone": "Europe/Berlin",
            "confirmed": True,
        }

        def worker(_):
            with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
                login = client.post(
                    "/operator/api/login",
                    json={"email": "operator@example.invalid", "password": PASSWORD},
                )
                assert login.status_code == 200
                response = client.post(
                    "/operator/api/family-creations",
                    json=request,
                    headers={"x-csrf-token": login.json()["csrf_token"]},
                )
                assert response.status_code in (201, 409)
                return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        assert 201 in results
        with registry.session() as db:
            jobs = list(db.scalars(select(FamilyCreation)))
            assert len(jobs) == 1 and jobs[0].status == "ready"
            assert db.get(Tenant, jobs[0].tenant_id).database_name == name
        with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
            assert (
                client.post(
                    "/api/auth/login",
                    json={"email": "created@example.invalid", "password": PASSWORD},
                ).status_code
                == 200
            )
            assert [member["name"] for member in client.get("/api/members").json()] == [
                "New parent"
            ]
            assert client.get("/operator/api/families").status_code == 401
        for database, role, secret in (
            (names[1], f"{name}_app", password),
            (name, f"{names[1]}_app", existing_password),
        ):
            forbidden = create_engine(
                settings.database_url(database).set(username=role, password=secret)
            )
            try:
                with pytest.raises(OperationalError), forbidden.connect():
                    pass
            finally:
                forbidden.dispose()
    finally:
        app.state.family_router.close()
        if engine:
            engine.dispose()
        with admin.connect() as connection:
            if made:
                connection.exec_driver_sql(f"DROP DATABASE {quoted_identifier(name)} WITH (FORCE)")
                connection.exec_driver_sql(f"DROP ROLE {quoted_identifier(name + '_app')}")
        admin.dispose()
