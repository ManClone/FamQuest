"""Level XP must not fall when spendable XP is used or deducted."""

from app.points import level_xp, spendable_xp
from app.db import SessionLocal
from tests.conftest import csrf
from tests.test_today import add_task, complete


def test_level_xp_ignores_manual_penalty_and_spending(client, parent, lena):
    task = add_task(client, parent, [lena], points=20)
    assert complete(client, parent, task, lena).status_code == 204
    with SessionLocal() as db:
        assert level_xp(db, lena) == 20
        assert spendable_xp(db, lena) == 20

    response = client.post(
        f"/api/members/{lena}/points",
        json={"amount": -5, "reason": "Konsequenz"},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        assert level_xp(db, lena) == 20
        assert spendable_xp(db, lena) == 15
