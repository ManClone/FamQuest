"""Exercise actual account roles and keep sanctions separate from base allowance."""

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.db import engine
from app.money import allowance_balance, post_weekly_allowance
from app.points import level_xp, spendable_xp
from tests.conftest import SATURDAY, csrf
from tests.test_today import add_task, complete


@pytest.mark.parametrize("role,expected", [("parent", 200), ("child", 403)])
def test_actual_account_role_controls_parent_endpoints(client, admin, lena, role, expected):
    credentials = {"email": f"{role}@example.org", "password": "sehr-geheim-456"}
    assert (
        client.post(
            "/api/auth/accounts", json={**credentials, "role": role}, headers=csrf(admin)
        ).status_code
        == 201
    )
    assert client.post("/api/auth/logout", headers=csrf(admin)).status_code == 204
    login = client.post("/api/auth/login", json=credentials)
    assert login.status_code == 200
    account = login.json()
    assert account["user"]["role"] == role
    assert account["parent_unlocked"] is (role == "parent")
    for url in (
        "/api/auth/accounts",
        "/api/approvals",
        f"/api/members/{lena}/money",
        f"/api/members/{lena}/money/settings",
        f"/api/members/{lena}/consequences",
        f"/api/members/{lena}/weekly-bonus?date={SATURDAY}",
    ):
        response = client.get(url)
        assert response.status_code == expected, (url, response.text)
    response = client.post(
        "/api/weekly-consequences/preview",
        json={
            "member_id": lena,
            "date": SATURDAY,
            "earned_bonus_cents": 100,
            "money_penalty_cents": 50,
        },
        headers=csrf(account),
    )
    assert response.status_code == expected, response.text


def test_excess_sanction_preserves_allowance_and_level_xp(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=20, money_cents=125)
    assert complete(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        assert post_weekly_allowance(db, lena, 500, dt.date(2026, 9, 28))
        db.commit()
    response = client.post(
        "/api/consequences",
        json={
            "member_id": lena,
            "title": "Test consequence",
            "effective_date": SATURDAY,
            "money_penalty_cents": 200,
            "xp_penalty": 30,
        },
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["xp_penalty_applied"] == 20
    bonus_url = f"/api/members/{lena}/weekly-bonus?date={SATURDAY}"
    preview = client.get(bonus_url)
    assert preview.status_code == 200
    assert preview.json()["earned_bonus_cents"] == 125
    assert preview.json()["payable_bonus_cents"] == 0
    with Session(engine) as db:
        assert allowance_balance(db, lena) == 500
        assert level_xp(db, lena) == 20
        assert spendable_xp(db, lena) == 0
    reverse_url = f"/api/consequences/{entry['id']}/reverse"
    for _ in range(2):
        assert client.post(reverse_url, headers=csrf(parent)).status_code == 200
    assert client.get(bonus_url).json()["payable_bonus_cents"] == 125
    with Session(engine) as db:
        assert allowance_balance(db, lena) == 500
        assert level_xp(db, lena) == 20
        assert spendable_xp(db, lena) == 20
