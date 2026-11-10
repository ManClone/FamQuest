"""Public authorization endpoints use browser consent and family-bound credentials."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth_registry import BrowserSession, OAuthClient, Tenant
from app.central_auth import create_app
from app.config import Settings
from app.oauth_http import install_oauth_routes
from app.oauth_tokens import authenticate_access
from tests import test_central_auth
from tests.test_central_auth import ORIGIN, PASSWORD

registry = test_central_auth.registry

CALLBACK = "https://client.example.invalid/callback"
VERIFIER = "v" * 64
RESOURCE = ORIGIN + "/mcp"


@pytest.fixture
def client(registry):
    settings = Settings(public_url=ORIGIN)
    app = create_app(settings, database=registry)
    install_oauth_routes(app, registry, settings)
    with registry.session() as db:
        db.add(OAuthClient(id="registered", redirect_uri=CALLBACK, enabled=True))
        db.commit()
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield client


def parameters():
    challenge = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    return {
        "client_id": "registered",
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "code_challenge_method": "S256",
        "code_challenge": challenge.rstrip(b"=").decode(),
        "resource": RESOURCE,
        "scope": "famquest:parent",
        "state": "unpredictable-client-state",
    }


def login(client, name="sertl"):
    response = client.post(
        "/api/auth/login",
        json={"email": f"{name}@example.invalid", "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def code(client):
    csrf = login(client)
    consent = client.get("/authorize", params=parameters())
    assert consent.status_code == 200, consent.text
    assert "Sertl" in consent.text
    assert "client.example.invalid" in consent.text
    assert "frame-ancestors 'none'" in consent.headers["content-security-policy"]
    assert (
        "form-action 'self' https://client.example.invalid;"
        in consent.headers["content-security-policy"]
    )
    response = client.post(
        "/authorize",
        data={**parameters(), "csrf_token": csrf, "decision": "allow"},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 303, response.text
    result = parse_qs(urlsplit(response.headers["location"]).query)
    assert result["state"] == [parameters()["state"]]
    assert result["iss"] == [ORIGIN]
    return result["code"][0]


def exchange(client, value, **overrides):
    return client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": "registered",
            "code": value,
            "redirect_uri": CALLBACK,
            "code_verifier": VERIFIER,
            "resource": RESOURCE,
            **overrides,
        },
    )


def test_discovery_and_default_closed_registration(client):
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["issuer"] == ORIGIN
    assert "registration_endpoint" not in metadata
    assert client.post("/register", json={"redirect_uris": [CALLBACK]}).status_code == 404
    assert client.get("/.well-known/oauth-protected-resource/mcp").json()["resource"] == RESOURCE
    response = client.get("/authorize", params=parameters())
    assert response.status_code == 303
    target = parse_qs(urlsplit(response.headers["location"]).query)["next"][0]
    assert target.startswith("/authorize?")


def test_consent_csrf_child_denial_and_untrusted_redirect(client):
    csrf = login(client)
    for changes in (
        {"redirect_uri": "https://attacker.invalid"},
        {"resource": "https://other/mcp"},
    ):
        response = client.get("/authorize", params={**parameters(), **changes})
        assert response.status_code == 400
        assert "location" not in response.headers
    assert (
        client.get("/authorize", params=[*parameters().items(), ("state", "other")]).status_code
        == 400
    )
    assert (
        client.post(
            "/authorize", data={**parameters(), "decision": "allow"}, headers={"origin": ORIGIN}
        ).status_code
        == 403
    )
    denied = client.post(
        "/authorize",
        data={**parameters(), "decision": "deny", "csrf_token": csrf},
        headers={"origin": ORIGIN},
    )
    assert parse_qs(urlsplit(denied.headers["location"]).query)["error"] == ["access_denied"]
    login(client, "henning")
    assert client.get("/authorize", params=parameters()).status_code == 403


def test_code_pkce_single_use_refresh_replay_and_revocation(client, registry):
    value = code(client)
    assert exchange(client, value, resource="https://other/mcp").json()["error"] == "invalid_target"
    assert exchange(client, value, code_verifier="x" * 64).json()["error"] == "invalid_grant"
    result = exchange(client, value)
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    pair = result.json()
    assert exchange(client, value).json()["error"] == "invalid_grant"
    with registry.session() as db:
        assert authenticate_access(db, pair["access_token"], audience=RESOURCE).tenant_id == 1
    refresh = {
        "grant_type": "refresh_token",
        "client_id": "registered",
        "resource": RESOURCE,
        "refresh_token": pair["refresh_token"],
    }
    rotated = client.post("/token", data=refresh)
    assert rotated.status_code == 200, rotated.text
    assert client.post("/token", data=refresh).json()["error"] == "invalid_grant"
    with registry.session() as db, pytest.raises(PermissionError):
        authenticate_access(db, rotated.json()["access_token"], audience=RESOURCE)
    pair = exchange(client, code(client)).json()
    assert (
        client.post(
            "/revoke", data={"client_id": "registered", "token": pair["access_token"]}
        ).status_code
        == 200
    )
    with registry.session() as db, pytest.raises(PermissionError):
        authenticate_access(db, pair["access_token"], audience=RESOURCE)


def test_disabled_family_and_malformed_requests(client, registry):
    value = code(client)
    with registry.session() as db:
        db.get(Tenant, 1).status = "disabled"
        db.commit()
    assert exchange(client, value).json()["error"] == "invalid_grant"
    for body in ("client_id=a&client_id=b", "a=" + "x" * 8192):
        response = client.post(
            "/token", content=body, headers={"content-type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 400
    assert client.post("/token", json={}).status_code == 400


def test_expired_browser_session_can_sign_in_again_without_losing_client_state(client, registry):
    login(client)
    with registry.session() as db:
        db.scalar(select(BrowserSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    response = client.get("/authorize", params=parameters())
    assert response.status_code == 303
    target = parse_qs(urlsplit(response.headers["location"]).query)["next"][0]
    assert parse_qs(urlsplit(target).query)["state"] == [parameters()["state"]]
    login(client)
    assert client.get("/authorize", params=parameters()).status_code == 200


def test_dynamic_registration_is_explicit_and_exact(registry):
    settings = Settings(public_url=ORIGIN, oauth_dynamic_registration=True)
    app = create_app(settings, database=registry)
    install_oauth_routes(app, registry, settings)
    with TestClient(app, base_url=ORIGIN) as client:
        for uri in (
            "http://client/callback",
            "https://client/*",
            "https://user:pass@client/cb",
            "https://client/cb#fragment",
            "https://client/cb\n",
        ):
            assert client.post("/register", json={"redirect_uris": [uri]}).status_code == 400
        result = client.post("/register", json={"redirect_uris": [CALLBACK]})
        assert result.status_code == 201, result.text
        with registry.session() as db:
            assert db.get(OAuthClient, result.json()["client_id"]).redirect_uri == CALLBACK
