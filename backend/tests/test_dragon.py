from fastapi.testclient import TestClient

from tests.conftest import csrf
from tests.test_personal_access import add_person


def test_existing_dragon_name_is_persistent_and_one_time(client, parent, lena):
    url = f"/api/members/{lena}/dragon"
    assert client.put(url, json={"name": "  Flämmchen  "}, headers=csrf(parent)).status_code == 200
    assert client.get(f"/api/members/{lena}/progress").json()["dragon_name"] == "Flämmchen"
    assert client.put(url, json={"name": "Flämmchen"}, headers=csrf(parent)).status_code == 200
    assert client.put(url, json={"name": "Other"}, headers=csrf(parent)).status_code == 409
    assert client.put(url, json={"name": " "}, headers=csrf(parent)).status_code == 422


def test_child_can_name_only_own_dragon(client, parent):
    one, credentials = add_person(client, parent, "Lena", "purple")
    two, _ = add_person(client, parent, "Tom", "green")
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert (
            child.put(
                f"/api/members/{two}/dragon", json={"name": "Wrong"}, headers=csrf(me)
            ).status_code
            == 403
        )
        assert (
            child.put(
                f"/api/members/{one}/dragon", json={"name": "Funki"}, headers=csrf(me)
            ).status_code
            == 200
        )
        assert child.get(f"/api/members/{one}/progress").json()["dragon_name"] == "Funki"
