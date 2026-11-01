"""Explicit smoke test ONLY for the isolated cluster created by staging_bootstrap."""

import json
import os
from contextlib import ExitStack
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import OperationalError

from app.auth_registry import Identity, Tenant
from app.config import Settings
from app.multitenant_app import create_app
from app.operator_setup import create_operator
from app.security import new_token
from app.staging_bootstrap import DATABASES, check_ready, inspect_cluster, validated_inputs


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


def run(settings=None, environ=None):
    settings = settings or Settings()
    accounts = validated_inputs(settings, os.environ if environ is None else environ)
    admin = create_engine(settings.database_url("postgres"))
    try:
        with admin.connect() as connection:
            require(inspect_cluster(connection, settings.public_url) == "ready", "staging marker")
    finally:
        admin.dispose()
    require(len(check_ready(settings)) == 2, "two-family preflight")
    app = create_app(settings)
    results = []
    created = []
    with ExitStack() as stack:
        clients = {}
        headers = {}
        for family in ("A", "B"):
            for role, prefix in (("PARENT", "eltern"), ("CHILD", "kind")):
                client = stack.enter_context(
                    TestClient(
                        app, base_url=settings.public_url, headers={"origin": settings.public_url}
                    )
                )
                key = (family, role)
                clients[key] = client
                response = client.post(
                    "/api/auth/login",
                    json={
                        "email": f"{prefix}.{family.lower()}@famquest.test",
                        "password": accounts[key],
                    },
                )
                require(response.status_code == 200, "staging login")
                headers[key] = {"x-csrf-token": response.json()["csrf_token"]}
                cookies = response.headers.get("set-cookie", "").lower()
                require("secure" in cookies and "httponly" in cookies, "secure session cookies")
                require(
                    client.get("/operator/api/families").status_code == 401,
                    "family session cannot access operator overview",
                )
        results.append("four_logins_and_secure_cookies")
        registry = app.state.auth_registry
        try:
            for family in ("A", "B"):
                child = clients[(family, "CHILD")]
                people = child.get("/api/members").json()
                require(
                    len(people) == 1 and people[0]["name"] == f"Kind {family}", "own child profile"
                )
                require(
                    child.get("/api/auth/accounts").status_code == 403,
                    "child cannot manage accounts",
                )
                require(
                    child.post(
                        "/api/todos",
                        json={"title": "denied", "icon": "fluent-emoji-flat:broom"},
                        headers=headers[(family, "CHILD")],
                    ).status_code
                    == 403,
                    "child write boundary",
                )
                parent = clients[(family, "PARENT")]
                require(len(parent.get("/api/members").json()) == 2, "family member count")
                marker = f"Staging {family} {uuid4().hex[:12]}"
                response = parent.post(
                    "/api/todos",
                    json={"title": marker, "icon": "fluent-emoji-flat:broom"},
                    headers=headers[(family, "PARENT")],
                )
                require(response.status_code == 201, "family-local create")
                created.append((family, response.json()["id"], marker))
            results.append("parent_child_roles")
            for family, _, marker in created:
                other = "B" if family == "A" else "A"
                require(
                    marker in json.dumps(clients[(family, "PARENT")].get("/api/chores").json()),
                    "own data visible",
                )
                require(
                    marker not in json.dumps(clients[(other, "PARENT")].get("/api/chores").json()),
                    "foreign data hidden",
                )
                spoofed = clients[(other, "PARENT")].get(
                    "/api/chores",
                    headers={
                        "x-family-id": family,
                        "x-family-database": DATABASES[0 if family == "A" else 1],
                    },
                )
                require(
                    marker not in json.dumps(spoofed.json()), "client headers cannot choose family"
                )
            results.append("business_data_isolation_and_header_spoofing")
            for source, target in ((0, 1), (1, 0)):
                credentials = settings.family_database_credentials[DATABASES[source]]
                engine = create_engine(
                    settings.database_url(DATABASES[target]).set(
                        username=credentials.username, password=credentials.password
                    )
                )
                try:
                    try:
                        with engine.connect() as connection:
                            connection.execute(text("SELECT 1"))
                    except OperationalError:
                        pass
                    else:
                        raise RuntimeError("foreign database role unexpectedly connected")
                finally:
                    engine.dispose()
            results.append("postgres_role_isolation")
            with registry.session() as control:
                tenant = control.scalar(select(Tenant).where(Tenant.database_name == DATABASES[0]))
                tenant_id = tenant.id
                tenant.status = "disabled"
                control.commit()
            try:
                for role in ("PARENT", "CHILD"):
                    require(
                        clients[("A", role)].get("/api/today").status_code in (401, 403),
                        "existing session disabled",
                    )
                require(
                    clients[("B", "PARENT")].get("/api/today").status_code == 200,
                    "other family stays active",
                )
            finally:
                with registry.session() as control:
                    control.execute(
                        update(Tenant).where(Tenant.id == tenant_id).values(status="active")
                    )
                    control.commit()
            results.append("disabled_family_blocks_existing_sessions")
        finally:
            for family, entry_id, _ in created:
                client = clients[(family, "PARENT")]
                response = client.get("/api/auth/me")
                require(response.status_code == 200, "family restored for cleanup")
                csrf = {"x-csrf-token": response.json()["csrf_token"]}
                require(
                    client.delete(f"/api/todos/{entry_id}", headers=csrf).status_code == 204,
                    "cleanup test todo",
                )
                require(client.post("/api/auth/logout").status_code == 403, "logout requires csrf")
                require(client.post("/api/auth/logout", headers=csrf).status_code == 204, "logout")
                require(client.get("/api/auth/me").status_code == 401, "session revoked")
        for family in ("A", "B"):
            child = clients[(family, "CHILD")]
            require(
                child.post("/api/auth/logout", headers=headers[(family, "CHILD")]).status_code
                == 204,
                "child logout",
            )
        results.append("csrf_logout_and_test_cleanup")
        operator_email = f"operator-{uuid4().hex}@famquest.test"
        operator_password = new_token()
        with registry.session() as control:
            operator = create_operator(control, operator_email, operator_password)
            operator_id = operator.id
            control.commit()
        try:
            operator_client = stack.enter_context(
                TestClient(
                    app, base_url=settings.public_url, headers={"origin": settings.public_url}
                )
            )
            response = operator_client.post(
                "/operator/api/login", json={"email": operator_email, "password": operator_password}
            )
            require(response.status_code == 200, "operator login")
            operator_csrf = response.json()["csrf_token"]
            listing = operator_client.get("/operator/api/families")
            require(
                listing.status_code == 200 and len(listing.json()) == 2,
                "operator two-family registry overview",
            )
            require(all(row["accounts"] == 2 for row in listing.json()), "operator account counts")
            require(
                operator_client.get("/api/members").status_code == 401,
                "operator cookie cannot access family data",
            )
            require(
                operator_client.post(
                    "/operator/api/logout", headers={"x-csrf-token": operator_csrf}
                ).status_code
                == 204,
                "operator logout",
            )
            require(
                operator_client.get("/operator/api/families").status_code == 401,
                "operator session revoked",
            )
        finally:
            with registry.session() as control:
                control.delete(control.get(Identity, operator_id))
                control.commit()
        results.append("separate_operator_overview_and_session_boundary")
    return results


def main():
    try:
        results = run()
    except Exception as exc:
        print(f"Isolated staging smoke failed ({type(exc).__name__}); no credentials printed.")
        raise SystemExit(1) from None
    print(json.dumps({"status": "passed", "checks": results}))


if __name__ == "__main__":
    main()
