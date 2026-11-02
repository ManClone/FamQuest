"""Explicit smoke test ONLY for the isolated cluster created by staging_bootstrap."""

import json
import os
from contextlib import ExitStack
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.exc import OperationalError

from app.auth_registry import FamilyCreation, Identity, OperatorSession, Tenant, TenantStatusEvent
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
            require(
                inspect_cluster(
                    connection,
                    settings.public_url,
                    (*DATABASES, *settings.family_creation_databases),
                )
                == "ready",
                "staging marker",
            )
    finally:
        admin.dispose()
    require(len(check_ready(settings)) >= 2, "two-family preflight")
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
                listing.status_code == 200 and len(listing.json()) >= 2,
                "operator two-family registry overview",
            )
            require(
                all(
                    row["accounts"] == 2
                    for row in listing.json()
                    if row["name"] in {"Testfamilie A", "Testfamilie B"}
                ),
                "operator account counts",
            )
            require(
                operator_client.get("/api/members").status_code == 401,
                "operator cookie cannot access family data",
            )
            target = next(row for row in listing.json() if row["name"] == "Testfamilie A")
            for key in (("A", "PARENT"), ("A", "CHILD"), ("B", "PARENT")):
                family, role = key
                prefix = "eltern" if role == "PARENT" else "kind"
                require(
                    clients[key]
                    .post(
                        "/api/auth/login",
                        json={
                            "email": f"{prefix}.{family.lower()}@famquest.test",
                            "password": accounts[key],
                        },
                    )
                    .status_code
                    == 200,
                    "fresh family login for status test",
                )
            action = {
                "expected_status": "active",
                "status": "disabled",
                "family_name": target["name"],
                "reason": "Isolated CI suspension test",
                "confirmed": True,
                "request_key": str(uuid4()),
            }
            path = f"/operator/api/families/{target['id']}/status"
            operator_headers = {"x-csrf-token": operator_csrf}
            first = operator_client.post(path, json=action, headers=operator_headers)
            require(first.status_code == 200, "audited family suspension")
            require(
                operator_client.post(path, json=action, headers=operator_headers).json()
                == first.json(),
                "status retry is idempotent",
            )
            for role in ("PARENT", "CHILD"):
                require(
                    clients[("A", role)].get("/api/today").status_code == 401,
                    "suspension revokes existing family session",
                )
            require(
                clients[("B", "PARENT")].get("/api/today").status_code == 200,
                "other family remains accessible",
            )
            other = next(row for row in listing.json() if row["name"] == "Testfamilie B")
            other_path = f"/operator/api/families/{other['id']}/status"
            other_action = {**action, "family_name": other["name"], "request_key": str(uuid4())}
            require(
                operator_client.post(
                    other_path, json=other_action, headers=operator_headers
                ).status_code
                == 200,
                "suspend second disposable family for recovery check",
            )
            auxiliary = [
                row
                for row in listing.json()
                if row["name"] not in {"Testfamilie A", "Testfamilie B"}
            ]
            for row in auxiliary:
                require(
                    operator_client.post(
                        f"/operator/api/families/{row['id']}/status",
                        json={**action, "family_name": row["name"], "request_key": str(uuid4())},
                        headers=operator_headers,
                    ).status_code
                    == 200,
                    "suspend disposable additional family for recovery test",
                )
            require(
                check_ready(settings) == [],
                "operator recovery preflight with all families disabled",
            )
            require(
                operator_client.post(
                    other_path,
                    json={
                        **other_action,
                        "expected_status": "disabled",
                        "status": "active",
                        "request_key": str(uuid4()),
                    },
                    headers=operator_headers,
                ).status_code
                == 200,
                "restore second disposable family",
            )
            for row in auxiliary:
                require(
                    operator_client.post(
                        f"/operator/api/families/{row['id']}/status",
                        json={
                            **action,
                            "family_name": row["name"],
                            "expected_status": "disabled",
                            "status": "active",
                            "request_key": str(uuid4()),
                        },
                        headers=operator_headers,
                    ).status_code
                    == 200,
                    "restore disposable additional family",
                )
            require(
                operator_client.post(
                    path,
                    json={
                        **action,
                        "expected_status": "disabled",
                        "status": "active",
                        "request_key": str(uuid4()),
                    },
                    headers=operator_headers,
                ).status_code
                == 200,
                "audited family reactivation",
            )
            require(
                clients[("A", "PARENT")].get("/api/today").status_code == 401,
                "reactivation does not resurrect a session",
            )
            require(
                clients[("A", "PARENT")]
                .post(
                    "/api/auth/login",
                    json={"email": "eltern.a@famquest.test", "password": accounts[("A", "PARENT")]},
                )
                .status_code
                == 200,
                "reactivated family permits a fresh login",
            )
            history = operator_client.get(f"/operator/api/families/{target['id']}/history").json()
            require(len(history["items"]) == 2, "one audit entry per real change")
            for client in clients.values():
                me = client.get("/api/auth/me")
                if me.status_code == 200:
                    require(
                        client.post(
                            "/api/auth/logout", headers={"x-csrf-token": me.json()["csrf_token"]}
                        ).status_code
                        == 204,
                        "status-test session cleanup",
                    )
            capacity = operator_client.get("/operator/api/capabilities").json()[
                "family_creation_capacity"
            ]
            require(capacity > 0, "prepared spare family capacity")
            new_email, new_password = f"created-{uuid4().hex}@famquest.test", new_token()
            creation = {
                "request_key": str(uuid4()),
                "family_name": f"Neue Testfamilie {uuid4().hex[:8]}",
                "parent_name": "Eltern Neu",
                "parent_email": new_email,
                "password": new_password,
                "language": "de",
                "timezone": "Europe/Berlin",
                "confirmed": True,
            }
            created_response = operator_client.post(
                "/operator/api/family-creations", json=creation, headers=operator_headers
            )
            require(
                created_response.status_code == 201
                and created_response.json()["status"] == "ready",
                "operator creates a family in its own prepared database",
            )
            require(
                operator_client.post(
                    "/operator/api/family-creations", json=creation, headers=operator_headers
                ).json()
                == created_response.json(),
                "family creation request is idempotent",
            )
            require(
                operator_client.get("/operator/api/capabilities").json()["family_creation_capacity"]
                == capacity - 1,
                "one family slot consumed",
            )
            new_parent = stack.enter_context(
                TestClient(
                    app, base_url=settings.public_url, headers={"origin": settings.public_url}
                )
            )
            login_response = new_parent.post(
                "/api/auth/login", json={"email": new_email, "password": new_password}
            )
            require(login_response.status_code == 200, "new family parent can log in")
            require(
                [member["name"] for member in new_parent.get("/api/members").json()]
                == ["Eltern Neu"],
                "new parent sees only own member",
            )
            require(
                new_parent.get("/operator/api/families").status_code == 401,
                "new parent is not operator",
            )
            marker = f"Creation isolation {uuid4().hex[:12]}"
            new_csrf = {"x-csrf-token": login_response.json()["csrf_token"]}
            todo = new_parent.post(
                "/api/todos",
                json={"title": marker, "icon": "fluent-emoji-flat:broom"},
                headers=new_csrf,
            )
            require(todo.status_code == 201, "new family can store business data")
            # Re-authenticate A after its test logout, then verify both directions.
            a_login = clients[("A", "PARENT")].post(
                "/api/auth/login",
                json={"email": "eltern.a@famquest.test", "password": accounts[("A", "PARENT")]},
            )
            require(a_login.status_code == 200, "existing family remains usable after creation")
            require(
                marker not in json.dumps(clients[("A", "PARENT")].get("/api/chores").json()),
                "new family data hidden from A",
            )
            require(
                new_parent.delete(f"/api/todos/{todo.json()['id']}", headers=new_csrf).status_code
                == 204,
                "new family test todo cleaned",
            )
            require(
                new_parent.post("/api/auth/logout", headers=new_csrf).status_code == 204,
                "new parent logout",
            )
            require(
                clients[("A", "PARENT")]
                .post("/api/auth/logout", headers={"x-csrf-token": a_login.json()["csrf_token"]})
                .status_code
                == 204,
                "A cleanup after creation test",
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
                # Disposable CI operator only; production API has no audit-delete route.
                control.execute(
                    delete(TenantStatusEvent).where(
                        TenantStatusEvent.actor_identity_id == operator_id
                    )
                )
                operator = control.get(Identity, operator_id)
                if control.scalar(
                    select(FamilyCreation.id)
                    .where(FamilyCreation.actor_identity_id == operator_id)
                    .limit(1)
                ):
                    # Keep creation provenance; disable its temporary CI actor.
                    operator.is_superadmin = False
                    operator.password_hash = "!"
                    control.execute(
                        delete(OperatorSession).where(OperatorSession.identity_id == operator_id)
                    )
                else:
                    control.delete(operator)
                control.commit()
        results.append("separate_operator_overview_and_session_boundary")
        results.append("audited_suspension_reactivation_and_permanent_session_revocation")
        results.append("operator_family_creation_login_and_business_data_isolation")
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
