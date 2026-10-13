from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import MoneyTransaction
from tests.test_today import add_task, complete, undo


def test_quest_bonus_double_tap_books_once(client, parent, lena, now):
    task = add_task(client, parent, [lena], money_cents=175)
    assert complete(client, parent, task, lena).status_code == 204
    assert complete(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        amounts = list(db.scalars(select(MoneyTransaction.amount_cents).where(MoneyTransaction.member_id == lena)))
    assert amounts == [175]
    assert undo(client, parent, task, lena).status_code == 204
    assert undo(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        amounts = list(db.scalars(select(MoneyTransaction.amount_cents).where(MoneyTransaction.member_id == lena).order_by(MoneyTransaction.id)))
    assert amounts == [175, -175]


def test_bonus_only_after_approval(client, parent, lena, now):
    from tests.conftest import csrf

    task = add_task(client, parent, [lena], money_cents=250, needs_approval=True)
    assert complete(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        assert list(db.scalars(select(MoneyTransaction.id))) == []

    pending = client.get("/api/approvals").json()
    assert len(pending) == 1
    approval_id = pending[0]["id"]
    assert client.post(f"/api/approvals/{approval_id}", headers=csrf(parent)).status_code == 204
    assert client.post(f"/api/approvals/{approval_id}", headers=csrf(parent)).status_code == 404
    with Session(engine) as db:
        assert list(db.scalars(select(MoneyTransaction.amount_cents))) == [250]


def test_rejected_bonus_is_not_booked(client, parent, lena, now):
    from tests.conftest import csrf

    task = add_task(client, parent, [lena], money_cents=300, needs_approval=True)
    assert complete(client, parent, task, lena).status_code == 204
    approval_id = client.get("/api/approvals").json()[0]["id"]
    assert client.delete(f"/api/approvals/{approval_id}", headers=csrf(parent)).status_code == 204
    with Session(engine) as db:
        assert list(db.scalars(select(MoneyTransaction.id))) == []


def test_bonus_and_unconditional_allowance_are_separate(client, parent, lena, now):
    from app.money import allowance_balance, bonus_balance, book_money, money_balance

    with Session(engine) as db:
        book_money(db, lena, 500, "allowance", "Wöchentliches Grundtaschengeld")
        book_money(db, lena, 150, "task_completed", "Bonusquest")
        db.commit()
        assert allowance_balance(db, lena) == 500
        assert bonus_balance(db, lena) == 150
        assert money_balance(db, lena) == 650

        book_money(db, lena, -150, "task_undone", "Bonusquest zurückgenommen")
        db.commit()
        assert allowance_balance(db, lena) == 500
        assert bonus_balance(db, lena) == 0
        assert money_balance(db, lena) == 500


def test_weekly_allowance_is_unconditional_and_idempotent(client, parent, lena, now):
    import datetime as dt

    from app.money import allowance_balance, post_weekly_allowance

    monday = dt.date(2026, 10, 5)
    with Session(engine) as db:
        assert post_weekly_allowance(db, lena, 500, monday) is True
        assert post_weekly_allowance(db, lena, 500, monday) is False
        db.commit()
        assert allowance_balance(db, lena) == 500

    # Quest completion and reversal cannot change the fixed allowance.
    task = add_task(client, parent, [lena], money_cents=125)
    assert complete(client, parent, task, lena).status_code == 204
    assert undo(client, parent, task, lena).status_code == 204
    with Session(engine) as db:
        assert allowance_balance(db, lena) == 500
        assert post_weekly_allowance(db, lena, 500, monday) is False
        assert post_weekly_allowance(db, lena, 500, monday + dt.timedelta(days=7)) is True
        db.commit()
        assert allowance_balance(db, lena) == 1000


def test_weekly_allowance_rejects_invalid_period_and_amount(client, parent, lena, now):
    import datetime as dt

    import pytest

    from app.money import post_weekly_allowance

    with Session(engine) as db:
        with pytest.raises(ValueError):
            post_weekly_allowance(db, lena, -100, dt.date(2026, 10, 5))
        with pytest.raises(ValueError):
            post_weekly_allowance(db, lena, 500, dt.date(2026, 10, 6))


def test_money_overview_is_parent_only_and_separates_balances(client, admin, parent, lena, now):
    from app.money import book_money

    with Session(engine) as db:
        book_money(db, lena, 500, "allowance", "weekly:2026-10-05")
        book_money(db, lena, 125, "task_completed", "Bonusquest")
        db.commit()

    response = client.get(f"/api/members/{lena}/money")
    assert response.status_code == 200
    assert response.json() == {
        "member_id": lena,
        "allowance_cents": 500,
        "bonus_cents": 125,
        "total_cents": 625,
    }

    from tests.conftest import csrf

    assert client.post("/api/parent/lock", headers=csrf(parent)).status_code == 200
    assert client.get(f"/api/members/{lena}/money").status_code == 403
