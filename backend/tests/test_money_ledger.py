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
