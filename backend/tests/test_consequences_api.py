"""Consequence API regression checks."""

from tests.conftest import csrf


def test_parent_can_book_and_reverse_consequence(client, parent, lena):
    payload = {
        "member_id": lena,
        "title": "Nicht auf Anweisungen gehört",
        "effective_date": "2026-10-14",
        "money_penalty_cents": 50,
        "xp_penalty": 5,
    }
    response = client.post("/api/consequences", json=payload, headers=csrf(parent))
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["xp_penalty_applied"] == 0
    assert entry["money_penalty_cents"] == 50
    url = f"/api/consequences/{entry['id']}/reverse"
    first = client.post(url, headers=csrf(parent))
    second = client.post(url, headers=csrf(parent))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reversed"] is True
