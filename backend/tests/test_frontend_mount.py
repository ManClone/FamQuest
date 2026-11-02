"""Both app factories can serve browser login without crossing the API boundary."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.frontend import mount_frontend
from app.multitenant_app import create_app
from tests import test_multitenant_app
from tests.test_central_auth import ORIGIN

environment = test_multitenant_app.environment


def assets(tmp_path):
    root = tmp_path / "frontend"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<h1>Browser login</h1>", encoding="utf-8")
    (root / "assets" / "app.js").write_text("// static asset", encoding="utf-8")
    return root


def test_integrated_browser_login_assets_and_api_boundaries(environment, tmp_path):
    _, registry, router, _ = environment
    app = create_app(
        Settings(public_url=ORIGIN, static_dir=assets(tmp_path), upload_dir=tmp_path),
        database=registry,
        family_router=router,
    )
    with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        assert "Browser login" in client.get("/login?next=%2Fauthorize%3Fstate%3Dabc").text
        assert "static asset" in client.get("/assets/app.js").text
        assert client.get("/.well-known/oauth-authorization-server").json()["issuer"] == ORIGIN
        assert client.get("/api/auth/me").status_code == 401
        test_multitenant_app.login(client, "Sertl")
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.json() == {"code": "common.not_found"}


def test_static_fallback_cannot_read_outside_frontend(tmp_path):
    root = assets(tmp_path)
    (tmp_path / "private.txt").write_text("private secret", encoding="utf-8")
    app = FastAPI()
    mount_frontend(app, root)
    with TestClient(app) as client:
        response = client.get("/%2e%2e/private.txt")
        assert "private secret" not in response.text
        assert "Browser login" in response.text
