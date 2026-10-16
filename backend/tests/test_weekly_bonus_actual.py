"""Regression tests for real weekly consequence calculations."""

from tests.conftest import csrf


def test_weekly_bonus_deducts_only_active_money_penalties(client, parent, lena):
    headers = csrf(parent)
    body = {
        "member_id": lena,
        "title": "Nicht auf Anweisungen gehört",
        "effective_date": "2026-10-14",
        "money_penalty_cents": 50,
        "xp_penalty": 5,
    }
    response = client.post("/api/consequences", json=body, headers=headers)
    assert response.status_code == 201, response.text
    url = f"/api/members/{lena}/weekly-bonus?date=2026-10-14"
    statement = client.get(url)
    assert statement.status_code == 200, statement.text
    assert statement.json()["money_penalty_cents"] == 50
    assert statement.json()["payable_bonus_cents"] == 0
    entry_id = response.json()["id"]
    assert client.post(f"/api/consequences/{entry_id}/reverse", headers=headers).status_code == 200
    updated = client.get(url)
    assert updated.status_code == 200
    assert updated.json()["money_penalty_cents"] == 0


def test_weekly_penalties_expire_at_monday(client, parent, lena):
    headers = csrf(parent)
    body = {
        "member_id": lena,
        "title": "Test",
        "effective_date": "2026-10-18",
        "money_penalty_cents": 75,
        "xp_penalty": 0,
    }
    assert client.post("/api/consequences", json=body, headers=headers).status_code == 201
    next_week = client.get(f"/api/members/{lena}/weekly-bonus?date=2026-10-19")
    assert next_week.status_code == 200
    assert next_week.json()["money_penalty_cents"] == 0
