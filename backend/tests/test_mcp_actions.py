"""Real write HTTP retries, concurrency and uncertain outcomes in separate family DBs."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import mcp_actions
from app.auth_registry import OAuthClient, Tenant
from app.models import Todo
from app.oauth_codes import issue_code
from app.oauth_pkce import s256_challenge
from app.oauth_tokens import exchange_code
from tests import test_multitenant_app
from tests.test_central_auth import ORIGIN

environment = test_multitenant_app.environment
BODY = {"title": "Take out recycling", "icon": "fluent-emoji-flat:broom"}


def bearer(registry, tenant):
    with registry.session() as db:
        client_id = f"client-{tenant}"
        db.add(OAuthClient(id=client_id, redirect_uri=ORIGIN + "/callback", enabled=True))
        db.commit()
        code = issue_code(
            db,
            client_id=client_id,
            redirect_uri=ORIGIN + "/callback",
            identity_id=tenant,
            tenant_id=tenant,
            code_challenge=s256_challenge("v" * 43),
        )
        db.commit()
        pair = exchange_code(
            db,
            code=code,
            client_id=client_id,
            redirect_uri=ORIGIN + "/callback",
            verifier="v" * 43,
            audience=ORIGIN + "/mcp",
        )
    return {"authorization": "Bearer " + pair.access_token}


def test_identical_retry_is_once_conflicts_rejected_and_family_keys_are_independent(environment):
    app, registry, router, _ = environment
    key = {"x-mcp-request-key": "action-" + "a" * 32}
    with (
        TestClient(app, base_url=ORIGIN, headers=bearer(registry, 1)) as sertl,
        TestClient(app, base_url=ORIGIN, headers=bearer(registry, 2)) as henning,
    ):
        assert sertl.post("/api/todos", json=BODY).status_code == 422
        created = sertl.post("/api/todos", json=BODY, headers=key)
        assert created.status_code == 201, created.text
        replay = sertl.post("/api/todos", json=BODY, headers=key)
        assert replay.status_code == 201
        assert replay.json() == created.json()
        assert (
            sertl.post(
                "https://other.example.invalid/api/todos", json=BODY, headers=key
            ).status_code
            == 403
        )
        assert (
            sertl.post("/api/todos", json={**BODY, "title": "Changed"}, headers=key).status_code
            == 409
        )
        other = henning.post("/api/todos", json=BODY, headers=key)
        assert other.status_code == 201, other.text
        assert sertl.post("/api/auth/accounts", json={}, headers=key).status_code == 403
        with registry.session() as db:
            db.get(Tenant, 1).status = "disabled"
            db.commit()
        assert sertl.post("/api/todos", json=BODY, headers=key).status_code == 401
    for engine in router.engines.values():
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Todo)) == 1


def test_simultaneous_retry_performs_one_actual_mutation(environment):
    app, registry, router, _ = environment
    with TestClient(app, base_url=ORIGIN, headers=bearer(registry, 1)) as client:

        def write(_):
            return client.post(
                "/api/todos", json=BODY, headers={"x-mcp-request-key": "b" * 32}
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(write, range(2)))
        assert 201 in statuses
        assert set(statuses) <= {201, 409}
    with Session(router.engines["famquest_sertl"]) as db:
        assert db.scalar(select(func.count()).select_from(Todo)) == 1


def test_lost_outcome_is_never_blindly_repeated(environment, monkeypatch):
    app, registry, router, _ = environment

    def fail(*args):
        raise RuntimeError("Simulated failure after business transaction committed")

    monkeypatch.setattr(mcp_actions, "finish", fail)
    with TestClient(
        app, base_url=ORIGIN, headers=bearer(registry, 1), raise_server_exceptions=False
    ) as client:
        key = {"x-mcp-request-key": "c" * 32}
        assert client.post("/api/todos", json=BODY, headers=key).status_code == 503
        replay = client.post("/api/todos", json=BODY, headers=key)
        assert replay.status_code == 409
        assert replay.json()["code"] == "mcp.outcome_unknown_check_state"
    with Session(router.engines["famquest_sertl"]) as db:
        assert db.scalar(select(func.count()).select_from(Todo)) == 1
