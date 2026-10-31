import datetime as dt
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db import engine
from app.models import ConsequenceEntry
from app.money import post_weekly_allowance
from tests.conftest import SATURDAY, csrf
from tests.test_today import add_task, complete, undo


def request(member, **changes):
    return {
        "member_id": member,
        "title": "Elternentscheidung",
        "severity": "heavy",
        "confirmed": True,
        "apply_money": False,
        "request_key": uuid4().hex,
        **changes,
    }


def test_no_bonus_no_money_and_no_legacy_arbitrary_penalty(client, parent, lena, now):
    headers = csrf(parent)
    response = client.post(
        "/api/consequences",
        json=request(lena, apply_money=True, expected_bonus_cents=0),
        headers=headers,
    )
    assert response.status_code == 409
    assert (
        client.post(
            "/api/consequences",
            json={
                "member_id": lena,
                "title": "Legacy",
                "xp_penalty": 100,
                "money_penalty_cents": 500,
            },
            headers=headers,
        ).status_code
        == 422
    )
    assert client.get(f"/api/members/{lena}/consequences").json() == []


def test_retry_is_idempotent_and_different_decision_with_same_key_rejected(
    client, parent, lena, now
):
    body = request(lena, severity="conversation")
    first = client.post("/api/consequences", json=body, headers=csrf(parent))
    second = client.post("/api/consequences", json=body, headers=csrf(parent))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["xp_penalty_applied"] == first.json()["money_penalty_cents"] == 0
    assert (
        client.post(
            "/api/consequences", json={**body, "title": "Andere Entscheidung"}, headers=csrf(parent)
        ).status_code
        == 409
    )


def test_zeroing_bonus_and_stale_parent_preview_are_rejected(client, parent, lena, now):
    task = add_task(client, parent, [lena], money_cents=100)
    assert complete(client, parent, task, lena).status_code == 204
    headers = csrf(parent)
    assert (
        client.post(
            "/api/consequences",
            json=request(lena, severity="severe", apply_money=True, expected_bonus_cents=100),
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/consequences",
            json=request(lena, apply_money=True, expected_bonus_cents=350),
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/consequences",
            json=request(lena, apply_money=True, expected_bonus_cents=100),
            headers=headers,
        ).status_code
        == 201
    )
    assert client.get(f"/api/members/{lena}/criticism").json()["payable_bonus_cents"] == 50


def test_confirmed_week_is_immutable_and_later_corrections_need_review(client, parent, lena, now):
    headers = csrf(parent)
    task = add_task(client, parent, [lena], points=10, money_cents=350)
    assert complete(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        post_weekly_allowance(db, lena, 500, dt.date(2026, 9, 28))
        db.commit()
    criticism = client.post(
        "/api/consequences",
        json=request(lena, apply_money=True, expected_bonus_cents=350),
        headers=headers,
    )
    assert criticism.status_code == 201, criticism.text
    state = client.get(f"/api/members/{lena}/criticism").json()
    assert state["allowance_cents"] == 500
    assert state["total_cents"] == 800
    close = {"date": SATURDAY, "confirmed": True, "expected_total_cents": 800}
    url = f"/api/members/{lena}/weekly-bonus/close"
    assert (
        client.post(url, json={**close, "expected_total_cents": 850}, headers=headers).status_code
        == 409
    )
    result = client.post(url, json=close, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["closed"] is True
    assert client.post(url, json=close, headers=headers).json()["total_cents"] == 800
    assert (
        client.post(
            "/api/consequences",
            json=request(lena, apply_money=True, expected_bonus_cents=300),
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/consequences/{criticism.json()['id']}/reverse",
            json={"confirmed": True, "reason": "Korrektur"},
            headers=headers,
        ).status_code
        == 409
    )
    assert undo(client, parent, task, lena).status_code == 204
    updated = client.get(f"/api/members/{lena}/criticism").json()
    assert updated["requires_review"] is True
    assert updated["total_cents"] == 800
    assert updated["payable_bonus_cents"] == 300


@pytest.mark.parametrize("date", ["2026-09-27", "2026-10-04"])
def test_past_week_or_future_criticism_refused(client, parent, lena, now, date):
    response = client.post(
        "/api/consequences", json=request(lena, effective_date=date), headers=csrf(parent)
    )
    assert response.status_code == 422


def test_reversal_restores_only_applied_stars_and_keeps_reason(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=1)
    assert complete(client, parent, task, lena).status_code == 204
    response = client.post(
        "/api/consequences", json=request(lena, severity="severe"), headers=csrf(parent)
    )
    assert response.status_code == 201, response.text
    assert response.json()["xp_penalty_requested"] == 3
    assert response.json()["xp_penalty_applied"] == 1
    url = f"/api/consequences/{response.json()['id']}/reverse"
    correction = {"confirmed": True, "reason": "Falsche Zuordnung"}
    assert client.post(url, json=correction, headers=csrf(parent)).status_code == 200
    assert client.post(url, json=correction, headers=csrf(parent)).status_code == 200
    assert client.get(f"/api/members/{lena}/points").json()["total"] == 1
    assert client.get(f"/api/members/{lena}/progress").json()["latest_deduction_id"] == 0
    with Session(engine) as db:
        assert db.get(ConsequenceEntry, response.json()["id"]).reversal_note == correction["reason"]
