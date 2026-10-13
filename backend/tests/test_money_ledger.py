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
