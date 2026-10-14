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


def test_money_overview_is_parent_only_and_separates_balances(client, parent, lena, now):
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


def test_parent_can_credit_weekly_allowance_only_once(client, parent, lena, now):
    from tests.conftest import csrf

    url = f"/api/members/{lena}/money/weekly-allowance"
    payload = {"amount_cents": 400, "week_start": "2026-10-05"}
    first = client.post(url, json=payload, headers=csrf(parent))
    assert first.status_code == 200, first.text
    assert first.json() == {
        "member_id": lena,
        "week_start": "2026-10-05",
        "booked": True,
        "allowance_cents": 400,
    }
    second = client.post(url, json=payload, headers=csrf(parent))
    assert second.status_code == 200, second.text
    assert second.json()["booked"] is False
    assert second.json()["allowance_cents"] == 400


def test_weekly_allowance_requires_parent_and_valid_monday(client, parent, lena, now):
    from tests.conftest import csrf

    url = f"/api/members/{lena}/money/weekly-allowance"
    assert client.post(
        url, json={"amount_cents": 400, "week_start": "2026-10-06"}, headers=csrf(parent)
    ).status_code == 422
    assert client.post("/api/parent/lock", headers=csrf(parent)).status_code == 200
    assert client.post(
        url, json={"amount_cents": 400, "week_start": "2026-10-05"}, headers=csrf(parent)
    ).status_code == 403


def test_weekly_batch_only_credits_configured_children_once(client, parent, lena, now):
    import datetime as dt
    from app.money import allowance_balance, due_weekly_allowances

    monday = dt.date(2026, 10, 5)
    with Session(engine) as db:
        assert due_weekly_allowances(db, {}, monday) == []
        assert allowance_balance(db, lena) == 0
        assert due_weekly_allowances(db, {lena: 450}, monday) == [lena]
        assert due_weekly_allowances(db, {lena: 450}, monday) == []
        db.commit()
        assert allowance_balance(db, lena) == 450

    with Session(engine) as db:
        assert due_weekly_allowances(db, {lena: 450}, monday) == []
        assert due_weekly_allowances(db, {lena: 450}, monday + dt.timedelta(days=7)) == [lena]
        db.commit()
        assert allowance_balance(db, lena) == 900


def test_money_overview_rejects_non_child(client, parent, now):
    from tests.conftest import csrf

    response = client.post(
        "/api/members",
        json={"name": "Elternteil", "role": "adult", "color": "blue"},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    adult = response.json()["id"]
    response = client.get(f"/api/members/{adult}/money")
    assert response.status_code == 422
    assert response.json()["code"] == "money.child_required"


def test_weekly_batch_validates_all_amounts_before_booking(client, parent, lena, now):
    import datetime as dt
    import pytest
    from app.money import allowance_balance, due_weekly_allowances

    monday = dt.date(2026, 10, 5)
    with Session(engine) as db:
        with pytest.raises(ValueError):
            due_weekly_allowances(db, {lena: 500, lena + 100: -1}, monday)
        assert allowance_balance(db, lena) == 0
        with pytest.raises(ValueError):
            due_weekly_allowances(db, {lena: 500}, monday + dt.timedelta(days=1))
        assert allowance_balance(db, lena) == 0


def test_weekly_allowance_is_not_affected_by_quest_bonus_reversal(client, parent, lena, now):
    import datetime as dt
    from app.money import allowance_balance, bonus_balance, post_weekly_allowance, book_money

    with Session(engine) as db:
        assert post_weekly_allowance(db, lena, 600, dt.date(2026, 10, 5))
        book_money(db, lena, 200, "task_completed", "Bonusquest")
        book_money(db, lena, -200, "task_undone", "Bonusquest undone")
        db.commit()
        assert allowance_balance(db, lena) == 600
        assert bonus_balance(db, lena) == 0


def test_weekly_allowance_does_not_credit_a_parent(client, parent, now):
    import datetime as dt
    import pytest
    from app.money import post_weekly_allowance
    from tests.conftest import csrf

    response = client.post(
        "/api/members",
        json={"name": "Erwachsener", "role": "adult", "color": "blue"},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    adult_id = response.json()["id"]
    with Session(engine) as db:
        with pytest.raises(ValueError, match="child"):
            post_weekly_allowance(db, adult_id, 500, dt.date(2026, 10, 5))
        assert list(db.scalars(select(MoneyTransaction.id).where(MoneyTransaction.member_id == adult_id))) == []


def test_weekly_allowance_status_is_read_only_and_idempotent(client, parent, lena, now):
    from tests.conftest import csrf

    url = f"/api/members/{lena}/money/weekly-allowance"
    params = {"week_start": "2026-10-05"}
    initial = client.get(url, params=params)
    assert initial.status_code == 200, initial.text
    assert initial.json()["booked"] is False
    credited = client.post(url, json={"amount_cents": 350, **params}, headers=csrf(parent))
    assert credited.status_code == 200, credited.text
    assert credited.json()["booked"] is True
    after = client.get(url, params=params)
    assert after.status_code == 200
    assert after.json()["booked"] is True
    assert client.get(url, params={"week_start": "2026-10-06"}).status_code == 422
