"""Full PostgreSQL schema, distinct login roles and actual business-route isolation."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth_registry import Identity, Membership, Tenant
from app.config import FamilyDatabaseCredentials, Settings
from app.family_db import FamilyDatabaseRouter
from app.models import Family, FamilyMember, User
from app.multitenant_app import create_app
from app.security import hash_secret
from app.tenant_provisioner import provision_empty_family
from app.tenant_provisioning import quoted_identifier
from tests.test_central_auth import ORIGIN, PASSWORD, TestRegistry


@pytest.fixture
def isolated_databases(tmp_path):
    settings = Settings()
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    suffix = uuid4().hex[:10]
    names = [f"famquest_isolation_{part}_{suffix}" for part in ("auth", "sertl", "henning")]
    created = []
    engines = []
    router = None
    password = "isolated-test-only-" + "x" * 32
    try:
        for index, name in enumerate(names):
            provision_empty_family(admin, name, password)
            created.append(name)
            url = settings.database_url(name).set(username=f"{name}_app", password=password)
            engine = create_engine(url)
            engines.append(engine)
            config_name = "auth_alembic.ini" if index == 0 else "alembic.ini"
            config = Config(Path(__file__).resolve().parents[1] / config_name)
            config.attributes["database_url"] = url
            config.attributes["configure_logger"] = False
            command.upgrade(config, "head")
        for index, name in enumerate(("Sertl", "Henning"), 1):
            with Session(engines[index]) as db:
                db.add(Family(id=1, name=name, default_language="de"))
                db.flush()
                db.add(
                    User(
                        id=1,
                        family_id=1,
                        email=f"{name.lower()}@example.invalid",
                        role="parent",
                        password_hash="!",
                    )
                )
                db.flush()
                db.add(
                    FamilyMember(
                        id=1, name=f"Parent {name}", role="parent", color="blue", user_id=1
                    )
                )
                db.commit()
        with Session(engines[0]) as db:
            hashed = hash_secret(PASSWORD)
            for index, name in enumerate(("Sertl", "Henning"), 1):
                db.add(
                    Identity(
                        id=index, email=f"{name.lower()}@example.invalid", password_hash=hashed
                    )
                )
                db.add(Tenant(id=index, name=name, database_name=names[index], status="active"))
            db.flush()
            db.add_all(
                [
                    Membership(identity_id=index, tenant_id=index, family_user_id=1, role="parent")
                    for index in (1, 2)
                ]
            )
            db.commit()
        settings = Settings(
            public_url=ORIGIN,
            upload_dir=tmp_path,
            family_database_credentials={
                name: FamilyDatabaseCredentials(username=f"{name}_app", password=password)
                for name in names[1:]
            },
        )
        router = FamilyDatabaseRouter(settings)
        app = create_app(settings, database=TestRegistry(engines[0]), family_router=router)
        yield app, names, password
    finally:
        if router is not None:
            router.close()
        for engine in engines:
            engine.dispose()
        with admin.connect() as conn:
            for name in reversed(created):
                conn.exec_driver_sql(f"DROP DATABASE {quoted_identifier(name)} WITH (FORCE)")
                conn.exec_driver_sql(f"DROP ROLE {quoted_identifier(name + '_app')}")
        admin.dispose()


def test_tasks_chores_and_database_roles_are_isolated(isolated_databases):
    app, names, password = isolated_databases
    with (
        TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as sertl,
        TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as henning,
    ):

        def login(client, name):
            result = client.post(
                "/api/auth/login", json={"email": f"{name}@example.invalid", "password": PASSWORD}
            )
            assert result.status_code == 200, result.text
            return {"x-csrf-token": result.json()["csrf_token"]}

        headers = login(sertl, "sertl")
        login(henning, "henning")
        room = sertl.post(
            "/api/chores/rooms",
            json={"name": "Sertl kitchen", "icon": "fluent-emoji-flat:broom"},
            headers=headers,
        )
        assert room.status_code == 201, room.text
        chore = sertl.post(
            "/api/chores",
            headers=headers,
            json={
                "room_id": room.json()["id"],
                "title": "Sertl private chore",
                "icon": "fluent-emoji-flat:broom",
                "interval_days": 7,
                "estimated_minutes": 20,
            },
        )
        assert chore.status_code == 201, chore.text
        assert sertl.get("/api/chores").json()["chores"][0]["title"] == "Sertl private chore"
        assert henning.get("/api/chores").json()["chores"] == []
        assert henning.get("/api/chores").json()["rooms"] == []
        assert sertl.get("/api/tasks").status_code == 200
        assert henning.get("/api/tasks").json() == []
        assert sertl.get("/api/routines").status_code == 200
        assert henning.get("/api/approvals").json() == []
        assert sertl.get("/api/maintenance/consistency").status_code == 200

    # A valid family-A login role cannot even connect to family B's database.
    engine = create_engine(
        Settings().database_url(names[2]).set(username=names[1] + "_app", password=password)
    )
    try:
        with pytest.raises(OperationalError), engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()
