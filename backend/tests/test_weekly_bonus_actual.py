"""Regression tests for real weekly consequence calculations."""

from uuid import uuid4

from tests.conftest import SATURDAY, csrf
from tests.test_today import add_task, complete


def test_weekly_bonus_deducts_only_active_money_penalties(client, parent, lena, now):
    headers = csrf(parent)
    body = {
        "member_id": lena,
        "title": "Nicht auf Anweisungen gehört",
        "severity": "heavy",
        "apply_money": True,
        "confirmed": True,
        "request_key": uuid4().hex,
        "expected_bonus_cents": 350,
    }
    task = add_task(client, parent, [lena], money_cents=350)
    assert complete(client, parent, task, lena).status_code == 204
    response = client.post("/api/consequences", json=body, headers=headers)
    assert response.status_code == 201, response.text
    url = f"/api/members/{lena}/weekly-bonus?date={SATURDAY}"
    statement = client.get(url)
    assert statement.status_code == 200, statement.text
    assert statement.json()["money_penalty_cents"] == 50
    assert statement.json()["payable_bonus_cents"] == 300
    entry_id = response.json()["id"]
    assert (
        client.post(
            f"/api/consequences/{entry_id}/reverse",
            json={"confirmed": True, "reason": "Korrektur"},
            headers=headers,
        ).status_code
        == 200
    )
    updated = client.get(url)
    assert updated.status_code == 200
    assert updated.json()["money_penalty_cents"] == 0


def test_weekly_penalties_expire_at_monday(client, parent, lena, now):
    headers = csrf(parent)
    body = {
        "member_id": lena,
        "title": "Test",
        "severity": "heavy",
        "apply_money": True,
        "confirmed": True,
        "request_key": uuid4().hex,
        "expected_bonus_cents": 125,
    }
    task = add_task(client, parent, [lena], money_cents=125)
    assert complete(client, parent, task, lena).status_code == 204
    assert client.post("/api/consequences", json=body, headers=headers).status_code == 201
    next_week = client.get(f"/api/members/{lena}/weekly-bonus?date=2026-10-05")
    assert next_week.status_code == 200
    assert next_week.json()["money_penalty_cents"] == 0
