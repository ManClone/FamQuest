"""Elternrechte ohne PIN und Familienverwaltung."""

from tests.conftest import csrf


def test_parent_settings_requires_login(client):
    response = client.put(
        "/api/parent/family",
        json={"name": "Familie Test", "default_language": "de", "timezone": "Europe/Berlin"},
    )
    assert response.status_code == 401


def test_parent_settings_available_immediately_after_login(client, admin):
    response = client.put(
        "/api/parent/family",
        json={"name": "  Familie Mond ", "default_language": "en", "timezone": "Europe/London"},
        headers=csrf(admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["family"] == {
        "name": "Familie Mond",
        "default_language": "en",
        "timezone": "Europe/London",
        "pin_enabled": False,
    }
    assert response.json()["parent_unlocked"] is True


def test_parent_settings_validate_fields(client, admin):
    response = client.put(
        "/api/parent/family",
        json={"name": "", "default_language": "de", "timezone": "Mars/Base"},
        headers=csrf(admin),
    )
    assert response.status_code == 422
    assert response.json()["fields"] == {
        "name": "validation.too_short",
        "timezone": "validation.invalid_timezone",
    }


def test_child_cannot_edit_family(client, admin):
    response = client.post(
        "/api/auth/accounts",
        json={"email": "tim@example.org", "password": "sehr-geheim-456", "role": "child"},
        headers=csrf(admin),
    )
    assert response.status_code == 201
    assert client.post("/api/auth/logout", headers=csrf(admin)).status_code == 204
    child = client.post(
        "/api/auth/login",
        json={"email": "tim@example.org", "password": "sehr-geheim-456"},
    ).json()
    response = client.put(
        "/api/parent/family",
        json={"name": "Familie Fremd", "default_language": "de", "timezone": "Europe/Berlin"},
        headers=csrf(child),
    )
    assert response.status_code == 403
