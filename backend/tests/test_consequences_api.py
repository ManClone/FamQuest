"""Consequence API regression checks."""

from uuid import uuid4

from tests.conftest import csrf


def test_parent_can_book_and_reverse_consequence(client, parent, lena, now):
    payload = {
        "member_id": lena,
        "title": "Nicht auf Anweisungen gehört",
        "severity": "heavy",
        "apply_money": False,
        "confirmed": True,
        "request_key": uuid4().hex,
    }
    response = client.post("/api/consequences", json=payload, headers=csrf(parent))
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["xp_penalty_applied"] == 0
    assert entry["money_penalty_cents"] == 0
    assert entry["xp_penalty_requested"] == 2
    url = f"/api/consequences/{entry['id']}/reverse"
    first = client.post(url, json={"confirmed": True, "reason": "Korrektur"}, headers=csrf(parent))
    second = client.post(url, json={"confirmed": True, "reason": "Korrektur"}, headers=csrf(parent))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reversed"] is True
