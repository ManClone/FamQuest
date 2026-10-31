"""Full PostgreSQL schema, distinct login roles and actual business-route isolation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth_identity_copy import align_registry_sequences
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
                for table in ("users", "family_members"):
                    db.execute(
                        text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), 1, true)")
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
            align_registry_sequences(db)
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
        henning_headers = login(henning, "henning")
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
        child = sertl.post(
            "/api/members",
            headers=headers,
            json={
                "name": "Tim",
                "role": "child",
                "color": "purple",
                "login": {"email": "tim@example.invalid", "password": "child-password-123"},
            },
        )
        assert child.status_code == 201, child.text
        assert len(sertl.get("/api/auth/accounts").json()) == 2
        assert len(henning.get("/api/auth/accounts").json()) == 1
        assert len(henning.get("/api/members").json()) == 1
        shared = {
            "name": "Shared",
            "role": "child",
            "color": "orange",
            "login": {"email": "shared@example.invalid", "password": "child-password-123"},
        }

        def create_person(item):
            client, csrf_headers = item
            return client.post("/api/members", json=shared, headers=csrf_headers).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create_person, [(sertl, headers), (henning, henning_headers)]))
        assert sorted(results) == [201, 409]
        assert len(sertl.get("/api/members").json()) == (3 if results[0] == 201 else 2)
        assert len(henning.get("/api/members").json()) == (2 if results[1] == 201 else 1)

        from tests.test_mcp_actions import BODY, bearer

        mcp_headers = bearer(app.state.auth_registry, 1)
        mcp_headers["x-mcp-request-key"] = "postgres-action-" + "a" * 32

        def create_once(_):
            return sertl.post("/api/todos", json=BODY, headers=mcp_headers).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create_once, range(2)))
        assert 201 in outcomes
        assert set(outcomes) <= {201, 409}
        assert sertl.post("/api/todos", json=BODY, headers=mcp_headers).status_code == 201
        assert len(sertl.get("/api/chores").json()["todos"]) == 1
        assert henning.get("/api/chores").json()["todos"] == []
        henning_mcp = bearer(app.state.auth_registry, 2)
        henning_mcp["x-mcp-request-key"] = mcp_headers["x-mcp-request-key"]
        assert henning.post("/api/todos", json=BODY, headers=henning_mcp).status_code == 201
        assert len(henning.get("/api/chores").json()["todos"]) == 1

        from sqlalchemy import func, select

        from app.deployment_check import migration_head, verify
        from app.family_db import FamilyDatabase
        from app.family_jobs import run_once
        from app.models import MoneyTransaction

        root = Path(__file__).resolve().parents[1]
        assert verify(
            app.state.auth_registry,
            app.state.family_router,
            auth_head=migration_head(root / "auth_alembic"),
            family_head=migration_head(root / "alembic"),
        ) == [1, 2]
        family = FamilyDatabase(1, names[1])
        with app.state.family_router.session(family) as db:
            db.get(FamilyMember, child.json()["id"]).weekly_allowance_cents = 500
            db.commit()
        for _ in range(2):
            run_once(
                app.state.auth_registry, app.state.family_router, allowances=True, calendar=False
            )
        with app.state.family_router.session(family) as db:
            assert (
                db.scalar(
                    select(func.sum(MoneyTransaction.amount_cents)).where(
                        MoneyTransaction.kind == "allowance"
                    )
                )
                == 500
            )

    # A valid family-A login role cannot even connect to family B's database.
    engine = create_engine(
        Settings().database_url(names[2]).set(username=names[1] + "_app", password=password)
    )
    try:
        with pytest.raises(OperationalError), engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()
