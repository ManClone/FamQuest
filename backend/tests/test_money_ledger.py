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
